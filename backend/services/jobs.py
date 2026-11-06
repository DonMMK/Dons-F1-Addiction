"""Bounded in-process read jobs for season analyses; predictions stay persistent."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="f1-analysis")
LOCK = threading.Lock()
JOBS = {}


def start(key, work):
    with LOCK:
        now = time.time()
        for job in JOBS.values():
            if job["key"] == key and (
                job["status"] == "running"
                or (job["status"] == "complete" and now - job["updated"] < 3600)
            ):
                return public(job)
        expired = [
            k
            for k, v in JOBS.items()
            if v["status"] != "running" and now - v["updated"] > 3600
        ]
        for item in expired:
            del JOBS[item]
        if len(JOBS) >= 10:
            complete = [
                (j["updated"], k) for k, j in JOBS.items() if j["status"] != "running"
            ]
            if not complete:
                raise ValueError(
                    "Analysis queue is full; retry when another season finishes"
                )
            del JOBS[min(complete)[1]]
        job = {
            "id": str(uuid4()),
            "key": key,
            "status": "running",
            "completed": 0,
            "total": 0,
            "data": None,
            "error": None,
            "updated": now,
        }
        JOBS[job["id"]] = job

    def progress(done, total):
        with LOCK:
            job.update(completed=done, total=total, updated=time.time())

    def run():
        try:
            result = work(progress)
            with LOCK:
                job.update(data=result, status="complete", updated=time.time())
        except Exception as exc:
            from fastapi import HTTPException

            message = (
                str(exc.detail)
                if isinstance(exc, HTTPException)
                else "Season data could not be loaded. Retry later."
            )
            with LOCK:
                job.update(
                    error=message,
                    status="failed",
                    updated=time.time(),
                )

    POOL.submit(run)
    return public(job)


def public(job):
    return {k: v for k, v in job.items() if k not in ("key", "updated")}


def get(job_id):
    with LOCK:
        return public(JOBS[job_id]) if job_id in JOBS else None

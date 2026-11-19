export interface TyrePoint {
  lap: number;
  age: number;
  stint: number;
  compound: string;
  seconds: number;
}

/** Normalise to race lap 1 under an explicit, user-supplied linear assumption. */
export function normaliseFuel(point: TyrePoint, gainPerLap: number) {
  return point.seconds + gainPerLap * (point.lap - 1);
}

/** Descriptive median pair slope within ONE stint, never physical tyre wear. */
export function stintDrift(points: TyrePoint[], gainPerLap: number) {
  if (
    points.length < 8 ||
    Math.max(...points.map((p) => p.age)) -
      Math.min(...points.map((p) => p.age)) <
      4
  )
    return null;
  const slopes: number[] = [];
  points.forEach((a, i) =>
    points.slice(i + 1).forEach((b) => {
      if (a.age !== b.age)
        slopes.push(
          (normaliseFuel(b, gainPerLap) - normaliseFuel(a, gainPerLap)) /
            (b.age - a.age),
        );
    }),
  );
  slopes.sort((a, b) => a - b);
  const mid = Math.floor(slopes.length / 2);
  return slopes.length
    ? slopes.length % 2
      ? slopes[mid]
      : (slopes[mid - 1] + slopes[mid]) / 2
    : null;
}

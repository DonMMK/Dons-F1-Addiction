import { Link } from 'react-router-dom'

const features = [
  {
    icon: '📊',
    title: 'Race Prediction',
    desc: 'Monte Carlo simulation engine with multiple model versions. Predict race winners from practice & qualifying data.',
    to: '/prediction',
  },
  {
    icon: '👻',
    title: 'Ghost Car Comparison',
    desc: 'Compare two drivers\' fastest laps head-to-head. Full telemetry overlay with speed, throttle, brake, and track map.',
    to: '/ghost-car',
  },
  {
    icon: '🏆',
    title: 'Best Car Analysis',
    desc: 'Which car dominated each era? Compare Mercedes W11, Red Bull RB19, and McLaren MCL39 across full seasons.',
    to: '/best-car',
  },
]

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <h1 className="hero__title">
          Data-Driven <span>F1</span> Analysis
        </h1>
        <p className="hero__subtitle">
          Predictions, telemetry comparisons, and performance analysis — all powered
          by real Formula 1 data from the FastF1 library.
        </p>
      </section>

      <section className="feature-grid">
        {features.map((f) => (
          <Link key={f.to} to={f.to} className="feature-card">
            <div className="feature-card__icon">{f.icon}</div>
            <h3 className="feature-card__title">{f.title}</h3>
            <p className="feature-card__desc">{f.desc}</p>
          </Link>
        ))}
      </section>
    </>
  )
}

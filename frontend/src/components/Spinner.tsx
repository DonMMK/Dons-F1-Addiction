export default function Spinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="loading-overlay">
      <span className="spinner" />
      {text}
    </div>
  )
}

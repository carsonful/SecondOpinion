import { useEffect, useState } from 'react'

function App() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus('backend unreachable'))
  }, [])

  return (
    <main>
      <h1>SecondOpinion</h1>
      <p>Busting health myths backed by science.</p>
      <p>Backend status: {status}</p>
    </main>
  )
}

export default App

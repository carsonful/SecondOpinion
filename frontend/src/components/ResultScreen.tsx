import { FormEvent } from 'react'
import { ClaimResult } from '../types'
import './ResultScreen.css'

interface ResultScreenProps {
  result: ClaimResult
  searchValue: string
  onSearchChange: (value: string) => void
  onSearch: (text: string) => void
}

export default function ResultScreen({ result, searchValue, onSearchChange, onSearch }: ResultScreenProps) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSearch(searchValue)
  }

  return (
    <section className="result">
      <form className="result__search" onSubmit={handleSubmit}>
        <input className="result__search-input" type="text" aria-label="Health claim"
          maxLength={2000} required value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)} placeholder="Enter another health claim" />
        <button className="result__search-button" type="submit">Find studies</button>
      </form>
      <h1 className="result__claim">“{result.claim}”</h1>
      <div className="result__summary glass-panel" role="status">
        <h2>Assessment pending</h2>
        <p>These are search results. They have not yet been assessed for whether they support or contradict your claim.</p>
        <p>Showing {result.evidence.articles.length} of {result.evidence.total_results} PubMed matches.</p>
        <details><summary>Search details</summary><p>{result.normalized.query}</p></details>
      </div>
      {result.evidence.articles.length === 0 && (
        <div className="result__summary glass-panel">
          <h2>No studies found</h2>
          <p>Try specifying the ingredient, treatment, or health outcome. No matches does not establish whether a claim is true or false.</p>
        </div>
      )}
      <div className="result__studies">
        {result.evidence.articles.map((article) => (
          <article className="result__study glass-panel" key={article.pmid}>
            <h2><a href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`} target="_blank" rel="noopener noreferrer">{article.title}</a></h2>
            <p className="result__metadata">{article.journal ?? 'Journal unavailable'} · {article.year ?? 'Year unavailable'} · PMID {article.pmid}</p>
            {article.retracted && <p className="result__retracted">Retracted publication — flagged by PubMed.</p>}
            <p className="result__metadata">{article.publication_types.join(' · ') || 'Publication type unavailable'}</p>
            {article.abstract ? <details><summary>Read abstract</summary><p className="result__abstract">{article.abstract}</p></details> : <p>Abstract unavailable — limited information.</p>}
          </article>
        ))}
      </div>
    </section>
  )
}

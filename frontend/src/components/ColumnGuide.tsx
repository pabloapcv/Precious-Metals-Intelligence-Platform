export function ColumnGuide({ items }: { items: Array<{ term: string; text: string }> }) {
  return (
    <dl className="column-guide">
      {items.map((item) => (
        <div key={item.term} className="column-guide-item">
          <dt>{item.term}</dt>
          <dd>{item.text}</dd>
        </div>
      ))}
    </dl>
  )
}

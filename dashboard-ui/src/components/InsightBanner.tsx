export function InsightBanner({ text }: { text: string }) {
  return (
    <div className="mb-4 rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
      <span className="mr-2">💡</span>
      {text}
    </div>
  );
}

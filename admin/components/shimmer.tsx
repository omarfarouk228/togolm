function S({ className }: { className: string }) {
  return (
    <div className={`animate-pulse bg-slate-200 rounded-lg ${className}`} />
  );
}

export function ShimmerStatCards({ count = 4 }: { count?: number }) {
  return (
    <div className={`grid gap-4 grid-cols-2 xl:grid-cols-${count}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
          <div className="flex items-center justify-between">
            <S className="h-3 w-24" />
            <S className="h-8 w-8 rounded-lg" />
          </div>
          <S className="h-7 w-20" />
          <S className="h-2.5 w-32" />
        </div>
      ))}
    </div>
  );
}

export function ShimmerChart() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <S className="h-4 w-40" />
      <S className="h-[240px] w-full rounded-xl" />
    </div>
  );
}

export function ShimmerTable({ rows = 8, cols = 4 }: { rows?: number; cols?: number }) {
  const widths = ["w-32", "w-24", "w-16", "w-28", "w-20", "w-24", "w-16"];
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <S key={i} className={`h-3 ${widths[i % widths.length]}`} />
        ))}
      </div>
      <div className="divide-y divide-slate-50">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="px-5 py-3.5 flex gap-4 items-center">
            {Array.from({ length: cols }).map((_, j) => (
              <S key={j} className={`h-3 ${widths[(i + j) % widths.length]}`} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ShimmerServiceCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {[0, 1].map((i) => (
        <div key={i} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <S className="h-9 w-9 rounded-lg" />
              <S className="h-4 w-24" />
            </div>
            <S className="h-5 w-14 rounded-full" />
          </div>
          <S className="h-3 w-full" />
          <S className="h-3 w-3/4" />
        </div>
      ))}
    </div>
  );
}

export function ShimmerCoverage() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div className="flex items-center gap-3">
        <S className="h-9 w-9 rounded-lg" />
        <S className="h-4 w-40" />
      </div>
      <S className="h-3 w-full" />
      <S className="h-3 rounded-full w-full" />
      <div className="flex justify-between">
        <S className="h-2.5 w-6" />
        <S className="h-2.5 w-10" />
        <S className="h-2.5 w-8" />
      </div>
    </div>
  );
}

export function ShimmerLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <div className="w-56 h-screen bg-slate-800 shrink-0 animate-pulse" />
      <main className="flex-1 overflow-y-auto bg-slate-50 p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          <S className="h-6 w-48" />
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <S key={i} className="h-28 rounded-xl" />
            ))}
          </div>
          <S className="h-64 rounded-xl" />
        </div>
      </main>
    </div>
  );
}

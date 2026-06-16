type ReadinessSparklineProps = {
  values: number[];
};

export function ReadinessSparkline({ values }: ReadinessSparklineProps) {
  const points = values.length > 1
    ? values.map((value, index) => {
        const x = (index / (values.length - 1)) * 100;
        const y = 100 - Math.max(0, Math.min(100, value));
        return `${x},${y}`;
      }).join(" ")
    : "";

  return (
    <svg viewBox="0 0 100 100" className="h-12 w-full">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        className="text-primary"
      />
      {values.map((value, index) => {
        const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
        const y = 100 - Math.max(0, Math.min(100, value));
        return <circle key={`${index}-${value}`} cx={x} cy={y} r="2.5" className="fill-primary" />;
      })}
    </svg>
  );
}

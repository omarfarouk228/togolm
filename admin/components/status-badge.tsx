"use client";

type BadgeVariant = "green" | "red" | "blue" | "purple" | "gray" | "yellow";

interface StatusBadgeProps {
  label: string;
  variant: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  green: "bg-green-100 text-green-700",
  red: "bg-red-100 text-red-700",
  blue: "bg-blue-100 text-blue-700",
  purple: "bg-purple-100 text-purple-700",
  gray: "bg-slate-100 text-slate-600",
  yellow: "bg-yellow-100 text-yellow-700",
};

export function StatusBadge({ label, variant }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${variantClasses[variant]}`}
    >
      {label}
    </span>
  );
}

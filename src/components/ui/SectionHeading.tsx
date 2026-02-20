import { cn } from "@/lib/utils";

interface SectionHeadingProps {
  title: string;
  subtitle?: string;
  align?: "left" | "center";
  className?: string;
}

export function SectionHeading({
  title,
  subtitle,
  align = "center",
  className,
}: SectionHeadingProps) {
  return (
    <div
      className={cn(
        "mb-10 sm:mb-16",
        align === "center" && "text-center",
        className
      )}
    >
      <h2 className="text-2xl font-bold tracking-tight sm:text-3xl md:text-5xl">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-4 max-w-2xl text-base text-text-secondary sm:text-lg mx-auto">
          {subtitle}
        </p>
      )}
    </div>
  );
}

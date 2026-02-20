import { cn } from "@/lib/utils";

interface SectionProps {
  id?: string;
  className?: string;
  children: React.ReactNode;
}

export function Section({ id, className, children }: SectionProps) {
  return (
    <section
      id={id}
      className={cn("py-20 px-4 md:py-32 md:px-8 max-w-7xl mx-auto", className)}
    >
      {children}
    </section>
  );
}

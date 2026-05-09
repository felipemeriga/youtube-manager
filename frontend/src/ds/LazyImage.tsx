import { useEffect, useRef, useState } from "react";
import { styled } from "@mui/material/styles";
import { palette, radius } from "./tokens";
import { Skeleton } from "./Skeleton";

const Wrap = styled("div")({
  position: "relative",
  width: "100%",
  height: "100%",
  background: palette.bg.inset,
  borderRadius: radius.md,
  overflow: "hidden",
});

const Img = styled("img")({
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
});

export interface LazyImageProps {
  src: string;
  alt: string;
  /** Widths used to build a srcset; the backend should support `?w=`. */
  widths?: number[];
  sizes?: string;
  fetchPriority?: "high" | "low" | "auto";
  rootMargin?: string;
  className?: string;
}

function buildSrcSet(src: string, widths: number[]): string {
  return widths
    .map((w) => {
      const url = new URL(src, window.location.origin);
      url.searchParams.set("w", String(w));
      return `${url.pathname}${url.search} ${w}w`;
    })
    .join(", ");
}

export function LazyImage({
  src,
  alt,
  widths,
  sizes,
  fetchPriority = "auto",
  rootMargin = "200px",
  className,
}: LazyImageProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [intersected, setIntersected] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!ref.current || intersected) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setIntersected(true);
          obs.disconnect();
        }
      },
      { rootMargin },
    );
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [intersected, rootMargin]);

  return (
    <Wrap ref={ref} className={className}>
      {!loaded && <Skeleton data-testid="lazyimage-skeleton" style={{ position: "absolute", inset: 0 }} />}
      {intersected && (
        <Img
          src={src}
          srcSet={widths && widths.length > 0 ? buildSrcSet(src, widths) : undefined}
          sizes={sizes}
          alt={alt}
          loading="lazy"
          decoding="async"
          // @ts-expect-error fetchpriority is a valid HTML attribute; React types lag.
          fetchpriority={fetchPriority}
          onLoad={() => setLoaded(true)}
        />
      )}
    </Wrap>
  );
}

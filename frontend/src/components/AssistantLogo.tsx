interface AssistantLogoProps {
  size?: number;
}

export default function AssistantLogo({ size = 16 }: AssistantLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Play triangle */}
      <polygon points="8,5 8,19 20,12" fill="white" opacity="0.95" />
      {/* Sparkle top-right */}
      <path
        d="M19,2 L20,5 L23,6 L20,7 L19,10 L18,7 L15,6 L18,5 Z"
        fill="white"
        opacity="0.8"
      />
      {/* Tiny sparkle */}
      <path
        d="M4,1 L4.8,3 L7,3.8 L4.8,4.6 L4,7 L3.2,4.6 L1,3.8 L3.2,3 Z"
        fill="white"
        opacity="0.5"
      />
    </svg>
  );
}

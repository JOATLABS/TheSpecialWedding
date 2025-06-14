import React from "react";

interface SectionWrapperProps {
  id: string;
  children: React.ReactNode;
  backgroundColor?: string;
}

export const SectionWrapper: React.FC<SectionWrapperProps> = ({
  id,
  children,
  backgroundColor = "bg-white bg-opacity-80 backdrop-blur-sm",
}) => {
  return (
    <section
      id={id}
      className={`py-24 px-4 ${backgroundColor} scroll-mt-20`}
    >
      {children}
    </section>
  );
};

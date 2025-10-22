import React from "react";

interface SectionWrapperProps {
  id: string;
  children: React.ReactNode;
  backgroundColor?: string;
  glassEffect?: boolean;
}

export const SectionWrapper: React.FC<SectionWrapperProps> = ({
  id,
  children,
  backgroundColor = "",
  glassEffect = false,
}) => {
  return (
    <section
      id={id}
      className={`py-6 md:py-8 px-4 scroll-mt-20 ${backgroundColor} ${
        glassEffect ? 'relative mb-4 md:mb-6' : ''
      }`}
    >
      {glassEffect && (
        <div 
          className="absolute inset-0 rounded-3xl mx-2 sm:mx-4 md:mx-8 lg:mx-12"
          style={{
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)',
            backdropFilter: 'blur(5px)',
            WebkitBackdropFilter: 'blur(5px)',
            border: '1px solid rgba(255, 255, 255, 0)',
            boxShadow: `
              0 8px 32px 0 rgba(31, 38, 135, 0.1),
              inset 0 0 0 1px rgba(255, 255, 255, 0.1)
            `,
          }}
        />
      )}
      <div className={glassEffect ? 'relative z-10' : ''}>
        {children}
      </div>
    </section>
  );
};

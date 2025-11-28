
import React from 'react';

// This is a simplified interface for the props of the ModernHeroSection component.
// It is based on the SaasFullConfig interface from app/admin/saas/page.tsx.
interface ModernHeroSectionProps {
  config: {
    hero_headline?: string;
    hero_subheadline?: string;
    hero_problem_statement?: string;
    hero_solution_statement?: string;
    hero_cta_primary: string;
    hero_cta_secondary: string;
    hero_screenshot_primary?: string;
    demo_video_url?: string;
    show_product_demo?: boolean;
  };
  onAuthModeChange: (mode: 'signup' | 'login') => void;
}

const ModernHeroSection: React.FC<ModernHeroSectionProps> = ({
  config,
  onAuthModeChange,
}) => {
  return (
    <section className="bg-white dark:bg-gray-900">
      <div className="grid max-w-screen-xl px-4 py-8 mx-auto lg:gap-8 xl:gap-0 lg:py-16 lg:grid-cols-12">
        <div className="mr-auto place-self-center lg:col-span-7">
          <h1 className="max-w-2xl mb-4 text-4xl font-extrabold tracking-tight leading-none md:text-5xl xl:text-6xl dark:text-white">
            {config.hero_headline}
          </h1>
          <p className="max-w-2xl mb-6 font-light text-gray-500 lg:mb-8 md:text-lg lg:text-xl dark:text-gray-400">
            {config.hero_subheadline}
          </p>
          <p className="max-w-2xl mb-6 font-light text-gray-500 lg:mb-8 md:text-lg lg:text-xl dark:text-gray-400">
            {config.hero_problem_statement}
          </p>
          <p className="max-w-2xl mb-6 font-light text-gray-500 lg:mb-8 md:text-lg lg:text-xl dark:text-gray-400">
            {config.hero_solution_statement}
          </p>
          <a
            href="#"
            onClick={() => onAuthModeChange('signup')}
            className="inline-flex items-center justify-center px-5 py-3 mr-3 text-base font-medium text-center text-white rounded-lg bg-primary-700 hover:bg-primary-800 focus:ring-4 focus:ring-primary-300 dark:focus:ring-primary-900"
          >
            {config.hero_cta_primary}
            <svg
              className="w-5 h-5 ml-2 -mr-1"
              fill="currentColor"
              viewBox="0 0 20 20"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                fillRule="evenodd"
                d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"
                clipRule="evenodd"
              ></path>
            </svg>
          </a>
          <a
            href="#"
            className="inline-flex items-center justify-center px-5 py-3 text-base font-medium text-center text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-100 focus:ring-4 focus:ring-gray-100 dark:text-white dark:border-gray-700 dark:hover:bg-gray-700 dark:focus:ring-gray-800"
          >
            {config.hero_cta_secondary}
          </a>
        </div>
        <div className="hidden lg:mt-0 lg:col-span-5 lg:flex">
          {config.show_product_demo && config.demo_video_url ? (
            <iframe
              className="w-full"
              src={config.demo_video_url}
              title="YouTube video player"
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            ></iframe>
          ) : (
            config.hero_screenshot_primary && (
              <img
                src={config.hero_screenshot_primary}
                alt="mockup"
              />
            )
          )}
        </div>
      </div>
    </section>
  );
};

export default ModernHeroSection;

import React from "react";

interface AnchorNavProps {
  sections: string[];
}

export const AnchorNav: React.FC<AnchorNavProps> = ({ sections }) => {
  return (
    <nav className="w-full px-2 sm:px-4 md:px-6 py-2 sm:py-3 md:py-4 bg-black bg-opacity-40 backdrop-blur-sm text-white fixed top-0 left-0 z-50 flex justify-center space-x-1 sm:space-x-2 md:space-x-4 lg:space-x-8">
      {sections.map((id) => (
        <a
          key={id}
          href={`#${id}`}
          className="text-[10px] sm:text-xs md:text-sm lg:text-base hover:underline focus:outline-none focus:ring focus:ring-white"
        >
          {id === 'venue' ? (
            <>
              <span className="sm:hidden">DETAILS</span>
              <span className="hidden sm:inline">WEDDING DETAILS</span>
            </>
          ) : id === 'story' ? (
            'OUR STORY'
          ) : (
            id.replace(/-/g, ' ').toUpperCase()
          )}
        </a>
      ))}
    </nav>
  );
};

import React from "react";

interface AnchorNavProps {
  sections: string[];
}

export const AnchorNav: React.FC<AnchorNavProps> = ({ sections }) => {
  // Split sections for mobile layout
  const firstRow = sections.slice(0, 3);
  const secondRow = sections.slice(3);

  const renderLink = (id: string) => (
    <a
      key={id}
      href={`#${id}`}
      className="text-sm sm:text-base md:text-lg hover:underline focus:outline-none focus:ring focus:ring-white px-2"
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
  );

  return (
    <nav className="w-full px-4 py-3 sm:py-4 bg-black bg-opacity-40 backdrop-blur-sm text-white fixed top-0 left-0 z-50">
      {/* Mobile: Two rows */}
      <div className="sm:hidden">
        <div className="flex justify-center space-x-3 mb-2">
          {firstRow.map(renderLink)}
        </div>
        <div className="flex justify-center space-x-3">
          {secondRow.map(renderLink)}
        </div>
      </div>
      
      {/* Desktop: Single row */}
      <div className="hidden sm:flex justify-center space-x-4 md:space-x-6 lg:space-x-8">
        {sections.map(renderLink)}
      </div>
    </nav>
  );
};

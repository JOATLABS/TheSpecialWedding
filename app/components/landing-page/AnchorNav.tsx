import React from "react";

interface AnchorNavProps {
  sections: string[];
}

export const AnchorNav: React.FC<AnchorNavProps> = ({ sections }) => {
  return (
    <nav className="w-full px-6 py-4 bg-black bg-opacity-40 backdrop-blur-sm text-white fixed top-0 left-0 z-50 flex justify-center space-x-8">
      {sections.map((id) => (
        <a
          key={id}
          href={`#${id}`}
          className="text-sm md:text-base hover:underline focus:outline-none focus:ring focus:ring-white"
        >
          {id === 'venue' ? 'WEDDING DETAILS' : id === 'story' ? 'OUR STORY' : id.replace(/-/g, ' ').toUpperCase()}
        </a>
      ))}
    </nav>
  );
};

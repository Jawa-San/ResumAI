import React from 'react';

const HomePage = () => {
  console.log('HomePage component is rendering!');
  
  return (
    <div style={{ padding: '2rem', backgroundColor: 'lightblue' }}>
      <h1>HOME PAGE WORKS!</h1>
      <p>Welcome to ResumAI!</p>
      <p>If you can see this, the Home component is working!</p>
    </div>
  );
};

export default HomePage;
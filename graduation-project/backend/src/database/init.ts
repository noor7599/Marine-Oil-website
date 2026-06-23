import pool from './pool.js';

export const initDatabase = async () => {
  try {
    console.log('Initializing database...');
    await pool.query('DROP TABLE IF EXISTS cases;');
    console.log('Dropped existing cases table');
    await pool.query('DROP TABLE IF EXISTS users;');
    console.log('Dropped existing users table');
    await pool.query(`
      CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);
    console.log('Created users table');
    await pool.query(`CREATE INDEX idx_users_email ON users(email);`);
    console.log('Created email index');

    // Cases table to store all uploaded cases with their metadata
    await pool.query(`
      CREATE TABLE cases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        run_id VARCHAR(255) NOT NULL,
        input_image_url VARCHAR(1024),
        confidence DECIMAL(5, 2),
        classification VARCHAR(50),
        oil_area_km2 DECIMAL(10, 4),
        is_oil BOOLEAN,
        risk_level VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, run_id)
      );
    `);
    console.log('Created cases table');
    await pool.query(`CREATE INDEX idx_cases_user_id ON cases(user_id);`);
    await pool.query(`CREATE INDEX idx_cases_created_at ON cases(created_at);`);
    console.log('Created cases indexes');
    
    console.log('Database initialization completed successfully!');
  } catch (error) {
    console.error('Database initialization failed:', error);
    throw error;
  }
};

// Only run directly when called as a script: `npm run db:init`
if (process.argv[1]?.includes('init')) {
  initDatabase().then(() => process.exit(0)).catch(() => process.exit(1));
}
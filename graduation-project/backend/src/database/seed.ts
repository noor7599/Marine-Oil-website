import pool from './pool.js';
import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';

const users = [
  'noorbarakat759@gmail.com',
  'mariamgad261@gmail.com',
  'esraaabuelkhir@gmail.com',
  'lobnaaahmed59@gmail.com',
  'mariamashrafazmy@gmail.com',
];

const PASSWORD = '12345';

export const seedDatabase = async () => {
  try {
    console.log('Seeding users...');
    const salt = await bcrypt.genSalt(10);
    const hash = await bcrypt.hash(PASSWORD, salt);

    for (const email of users) {
      const id = uuidv4();
      await pool.query(
        'INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3) ON CONFLICT (email) DO NOTHING',
        [id, email, hash]
      );
      console.log(`Inserted ${email}`);
    }
    console.log('Seeding complete.');
  } catch (err) {
    console.error('Error seeding users', err);
    throw err;
  }
};

// Only run directly when called as a script: `npm run db:seed`
if (process.argv[1]?.includes('seed')) {
  seedDatabase().then(() => process.exit(0)).catch(() => process.exit(1));
}
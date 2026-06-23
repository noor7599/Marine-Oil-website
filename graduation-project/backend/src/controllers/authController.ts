import { Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import pool from '../database/pool.js';
import { LoginRequest, AuthResponse } from '../types/index.js';

const JWT_SECRET = process.env.JWT_SECRET || 'your_secret_key';
const JWT_EXPIRY = process.env.JWT_EXPIRY || '7d';

export const register = async (req: Request, res: Response): Promise<void> => {
  try {
    const { email, password } = req.body as LoginRequest;

    // Validate input
    if (!email || !password) {
      res.status(400).json({
        success: false,
        message: 'Email and password are required',
      });
      return;
    }

    // Check if user already exists
    const existingUser = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    if (existingUser.rows.length > 0) {
      res.status(409).json({
        success: false,
        message: 'User already exists with this email',
      });
      return;
    }

    // Hash password
    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(password, salt);

    // Create user
    const userId = uuidv4();
    await pool.query(
      'INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)',
      [userId, email, passwordHash]
    );

    // Generate JWT token
    const token = jwt.sign({ userId, email }, JWT_SECRET, { expiresIn: JWT_EXPIRY } as any);

    const response: AuthResponse = {
      success: true,
      message: 'User registered successfully',
      token,
      user: {
        id: userId,
        email,
      },
    };

    res.status(201).json(response);
  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred during registration',
    });
  }
};

export const login = async (req: Request, res: Response): Promise<void> => {
  try {
    const { email, password } = req.body as LoginRequest;
    console.log('Login attempt:', email);
    // Validate input
    if (!email || !password) {
      res.status(400).json({
        success: false,
        message: 'Email and password are required',
      });
      return;
    }

    // Find user
    const result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    const user = result.rows[0];

    if (!user) {
      res.status(401).json({
        success: false,
        message: 'Invalid email or password',
      });
      return;
    }

    // Compare password
    const isPasswordValid = await bcrypt.compare(password, user.password_hash);

    if (!isPasswordValid) {
      res.status(401).json({
        success: false,
        message: 'Invalid email or password',
      });
      return;
    }

    // Generate JWT token
    const token = jwt.sign({ userId: user.id, email: user.email }, JWT_SECRET, {
      expiresIn: JWT_EXPIRY,
    } as any);

    const response: AuthResponse = {
      success: true,
      message: 'Login successful',
      token,
      user: {
        id: user.id,
        email: user.email,
      },
    };

    res.json(response);
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred during login',
    });
  }
};

export const verify = async (req: Request, res: Response): Promise<void> => {
  try {
    if (!req.user) {
      res.status(401).json({
        success: false,
        message: 'Not authenticated',
      });
      return;
    }

    res.json({
      success: true,
      message: 'Token is valid',
      user: {
        id: req.user.userId,
        email: req.user.email,
      },
    });
  } catch (error) {
    console.error('Verify error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred during verification',
    });
  }
};

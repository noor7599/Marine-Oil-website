import { Router } from 'express';
import { login, register, verify } from '../controllers/authController.js';
import { authMiddleware } from '../middleware/auth.js';

const router = Router();

router.post('/login', login);
router.post('/register', register);
router.get('/verify', authMiddleware, verify);

export default router;

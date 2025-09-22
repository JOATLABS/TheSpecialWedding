import { config } from 'dotenv';
import { resolve } from 'path';

// Load environment variables from .env file
config({ path: resolve(__dirname, '../.env') });

export const testConfig = {
  adminCredentials: {
    email: process.env.PRIMARY_ADMIN_EMAIL || '',
    password: process.env.PRIMARY_ADMIN_PASSWORD || ''
  },
  baseUrls: {
    frontend: 'http://localhost:3002',
    backend: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002'
  },
  timeouts: {
    default: 10000,
    navigation: 30000,
    assertion: 5000
  }
};

// Validate required environment variables
if (!testConfig.adminCredentials.email || !testConfig.adminCredentials.password) {
  throw new Error('Missing required environment variables: PRIMARY_ADMIN_EMAIL and PRIMARY_ADMIN_PASSWORD must be set in .env file');
}
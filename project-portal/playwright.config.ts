import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests/e2e',use:{baseURL:'http://127.0.0.1:4317',browserName:'chromium',channel:'chrome',headless:true},workers:1,reporter:'list',timeout:30000});

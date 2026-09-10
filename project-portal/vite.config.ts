import {defineConfig} from 'vite';
export default defineConfig({server:{host:'127.0.0.1',watch:{ignored:['**/.verification/**','**/test-results/**','**/data/generated/**']},fs:{strict:true,deny:['**/.env*','**/.git/**','**/.verification/**','**/data/**','**/*.pem']}},build:{sourcemap:false}});

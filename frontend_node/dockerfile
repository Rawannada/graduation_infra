# استخدمي نسخة Node خفيفة
FROM node:20-alpine

WORKDIR /app

# نسخ ملفات الـ package أولاً لسرعة التحميل
COPY package*.json ./

RUN npm install

# نسخ باقي ملفات المشروع
COPY . .

# Vite بيشتغل على بورت 5173
EXPOSE 5173

# أمر التشغيل للـ Development
CMD ["npm", "run", "dev", "--", "--host"]
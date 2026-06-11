FROM node:20-alpine

WORKDIR /app

# Instalar dependencias primero (capa cacheada)
COPY package*.json ./
RUN npm install

# Copiar código fuente
COPY . .

EXPOSE 5173

# Vite dev server con hot-reload
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

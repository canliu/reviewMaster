FROM node:22-bookworm-slim

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

# Install dependencies first so the layer is cacheable across source edits.
COPY package.json ./
# package-lock.json is optional in dev — `npm install` will create one in the
# image layer. Stage 7 will switch the prod image to `npm ci` against a
# committed lockfile.
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]

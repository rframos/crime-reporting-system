CREATE TABLE incidents (
  id SERIAL PRIMARY KEY,
  type VARCHAR(50),
  description TEXT,
  latitude FLOAT,
  longitude FLOAT,
  image_url TEXT,
  classification VARCHAR(50),
  confidence FLOAT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

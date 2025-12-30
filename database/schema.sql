CREATE TABLE incidents (
  id SERIAL PRIMARY KEY,
  type VARCHAR(50),              -- e.g., theft, vandalism, accident
  description TEXT,               -- details of the incident
  latitude FLOAT,                 -- location latitude
  longitude FLOAT,                -- location longitude
  image_url TEXT,                 -- path to uploaded image
  classification VARCHAR(50),     -- CNN model output
  confidence FLOAT,               -- CNN confidence score
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  role VARCHAR(20) CHECK (role IN ('admin','resident','barangay','police')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

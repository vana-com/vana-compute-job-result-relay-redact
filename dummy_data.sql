-- Create the tables in accordance to the relevant Data Refiner schema
CREATE TABLE users (
    user_id VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    locale VARCHAR NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (email)
);

-- Seed dummy data representing ingested, refined Query Engine data points
INSERT INTO users (user_id, email, name, locale, created_at) VALUES
('u001', 'alice@example.com', 'Alice Smith', 'en_US', '2024-04-01 09:00:00'),
('u002', 'bob@example.com', 'Bob Johnson', 'en_GB', '2024-04-01 10:15:00'),
('u003', 'carol@example.com', 'Carol Lee', 'fr_FR', '2024-04-01 11:30:00'),
('u004', 'dave@example.com', 'Dave Kim', 'de_DE', '2024-04-01 12:45:00'),
('u005', 'eve@example.com', 'Eve Torres', 'es_ES', '2024-04-01 13:00:00'),
('u006', 'frank@example.com', 'Frank Wu', 'it_IT', '2024-04-01 14:20:00'),
('u007', 'grace@example.com', 'Grace Hall', 'pt_BR', '2024-04-01 15:35:00'),
('u008', 'heidi@example.com', 'Heidi Müller', 'nl_NL', '2024-04-01 16:50:00'),
('u009', 'ivan@example.com', 'Ivan Petrov', 'ru_RU', '2024-04-01 17:10:00'),
('u010', 'judy@example.com', 'Judy Alvarez', 'ja_JP', '2024-04-01 18:25:00');

-- Create the `results` table to simulate Query Engine query processing results.
-- (The SELECT query is what would be submitted to the Compute Engine with the job.)
CREATE TABLE results AS
SELECT
    user_id,
    locale
FROM users; 
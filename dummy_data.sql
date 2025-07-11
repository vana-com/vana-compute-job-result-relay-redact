-- Create the tables in accordance to the relevant Data Refiner schema
CREATE TABLE users (
    user_id VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    phone_number VARCHAR,
    address VARCHAR,
    ssn VARCHAR,
    credit_card VARCHAR,
    date_of_birth DATE,
    bio TEXT,
    locale VARCHAR NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (email)
);

-- Seed dummy data representing ingested, refined Query Engine data points with PII
INSERT INTO users (user_id, email, name, phone_number, address, ssn, credit_card, date_of_birth, bio, locale, created_at) VALUES
('u001', 'alice.smith@example.com', 'Alice Smith', '555-123-4567', '123 Main St, New York, NY 10001', '437-84-9201', '4532-1234-5678-9012', '1985-03-15', 'Alice Smith is a software engineer living in New York. She can be reached at alice.smith@example.com or 555-123-4567.', 'en_US', '2024-04-01 09:00:00'),
('u002', 'bob.johnson@example.com', 'Bob Johnson', '555-234-5678', '456 Oak Ave, London, UK', '521-96-7340', '5555-4444-3333-2222', '1990-07-22', 'Bob Johnson works for Microsoft and lives in London. Contact him at bob.johnson@example.com. His phone is 555-234-5678.', 'en_GB', '2024-04-01 10:15:00'),
('u003', 'carol.lee@example.com', 'Carol Lee', '555-345-6789', '789 Pine Rd, Paris, France', '602-18-5437', '4111-1111-1111-1111', '1988-11-03', 'Dr. Carol Lee is a researcher. Her email is carol.lee@example.com and phone 555-345-6789. She was born on November 3, 1988.', 'fr_FR', '2024-04-01 11:30:00'),
('u004', 'dave.kim@example.com', 'Dave Kim', '555-456-7890', '321 Elm St, Berlin, Germany', '719-42-8063', '3782-8224-6310-0052', '1992-12-25', 'Dave Kim, a German resident, can be contacted at dave.kim@example.com or 555-456-7890. His SSN is 719-42-8063.', 'de_DE', '2024-04-01 12:45:00'),
('u005', 'eve.torres@example.com', 'Eve Torres', '555-567-8901', '654 Maple Dr, Madrid, Spain', '834-75-2196', '6011-1111-1111-1117', '1987-05-14', 'Eve Torres lives in Madrid, Spain. You can reach her at eve.torres@example.com or call 555-567-8901. Born May 14, 1987.', 'es_ES', '2024-04-01 13:00:00'),
('u006', 'frank.wu@example.com', 'Frank Wu', '555-678-9012', '987 Cedar Ln, Rome, Italy', '945-61-3528', '5105-1051-0510-5100', '1991-08-30', 'Frank Wu is an Italian citizen. Email: frank.wu@example.com, Phone: 555-678-9012. His address is 987 Cedar Ln, Rome, Italy.', 'it_IT', '2024-04-01 14:20:00'),
('u007', 'grace.hall@example.com', 'Grace Hall', '555-789-0123', '147 Birch St, São Paulo, Brazil', '167-89-4073', '4000-0000-0000-0002', '1989-02-11', 'Grace Hall from São Paulo can be reached at grace.hall@example.com or 555-789-0123. DOB: February 11, 1989.', 'pt_BR', '2024-04-01 15:35:00'),
('u008', 'heidi.muller@example.com', 'Heidi Müller', '555-890-1234', '258 Spruce Ave, Amsterdam, Netherlands', '283-50-7419', '3530-1113-3333-0000', '1986-09-18', 'Heidi Müller lives in Amsterdam. Contact: heidi.muller@example.com or 555-890-1234. Her credit card ends in 0000.', 'nl_NL', '2024-04-01 16:50:00'),
('u009', 'ivan.petrov@example.com', 'Ivan Petrov', '555-901-2345', '369 Willow Rd, Moscow, Russia', '394-07-6852', '4444-3333-2222-1111', '1993-06-07', 'Ivan Petrov from Moscow, Russia. Email ivan.petrov@example.com, phone 555-901-2345. IP address: 192.168.1.100.', 'ru_RU', '2024-04-01 17:10:00'),
('u010', 'judy.alvarez@example.com', 'Judy Alvarez', '555-012-3456', '741 Ash Blvd, Tokyo, Japan', '508-23-9617', '3782-8224-6310-0037', '1994-01-28', 'Judy Alvarez in Tokyo. Visit her website at https://judy.example.com or email judy.alvarez@example.com. Phone: 555-012-3456.', 'ja_JP', '2024-04-01 18:25:00');

-- Create the `results` table to simulate Query Engine query processing results.
-- (The SELECT query is what would be submitted to the Compute Engine with the job.)
CREATE TABLE results AS
SELECT *
FROM users; 
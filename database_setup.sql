-- 1️⃣ Students Table
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roll_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    section TEXT NOT NULL,
    year INT NOT NULL,
    hackerrank_username TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2️⃣ Leaderboard Table
CREATE TABLE leaderboard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contest_name TEXT NOT NULL,
    contest_date DATE,
    username TEXT NOT NULL,
    score INT,
    time_taken INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ⚡ Indexes for Join Optimization
CREATE INDEX idx_student_username ON students(hackerrank_username);
CREATE INDEX idx_leaderboard_username ON leaderboard(username);

-- ==========================================
-- 📊 RPC Functions for Analytics Queries
-- ==========================================
-- Supabase REST API does not support raw SQL queries or JOINs without Foreign Keys directly.
-- Using RPCs (Remote Procedure Calls) allows us to execute these complex queries via the API.

-- 1. Department leaderboard
CREATE OR REPLACE FUNCTION get_department_leaderboard()
RETURNS TABLE (department TEXT, total_score BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.department, SUM(l.score) as total_score
    FROM leaderboard l
    JOIN students s ON l.username = s.hackerrank_username
    GROUP BY s.department
    ORDER BY total_score DESC;
END;
$$ LANGUAGE plpgsql;

-- 2. Section leaderboard
CREATE OR REPLACE FUNCTION get_section_leaderboard()
RETURNS TABLE (section TEXT, total_score BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.section, SUM(l.score) as total_score
    FROM leaderboard l
    JOIN students s ON l.username = s.hackerrank_username
    GROUP BY s.section
    ORDER BY total_score DESC;
END;
$$ LANGUAGE plpgsql;

-- 3. Top Students
CREATE OR REPLACE FUNCTION get_top_students()
RETURNS TABLE (name TEXT, total_score BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.name, SUM(l.score) as total_score
    FROM leaderboard l
    JOIN students s ON l.username = s.hackerrank_username
    GROUP BY s.name
    ORDER BY total_score DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- 4. Students who did NOT participate
CREATE OR REPLACE FUNCTION get_absent_students(p_contest_name TEXT)
RETURNS TABLE (id UUID, name TEXT, dept TEXT, section TEXT, year INT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.name, s.department as dept, s.section, s.year
    FROM students s
    WHERE s.hackerrank_username NOT IN (
        SELECT l.username
        FROM leaderboard l
        WHERE l.contest_name = p_contest_name
    );
END;
$$ LANGUAGE plpgsql;

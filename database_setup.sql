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

-- 6. Get all students with their contest participation
CREATE OR REPLACE FUNCTION get_all_students_with_contests()
RETURNS TABLE (
    id UUID,
    roll_no TEXT,
    name TEXT,
    department TEXT,
    section TEXT,
    year INT,
    hackerrank_username TEXT,
    contests JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.roll_no,
        s.name,
        s.department,
        s.section,
        s.year,
        s.hackerrank_username,
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'contest_name', l.contest_name,
                    'score', l.score,
                    'time_taken', l.time_taken
                )
            ) FILTER (WHERE l.id IS NOT NULL), '[]'::jsonb
        ) as contests
    FROM students s
    LEFT JOIN leaderboard l ON s.hackerrank_username = l.username
    GROUP BY s.id
    ORDER BY s.roll_no;
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- 🛠️ Platform Tracking & LeetCode Stats
-- ==========================================

-- 7. Platform IDs Table
CREATE TABLE student_platforms (
    roll_no TEXT PRIMARY KEY,
    leetcode_id TEXT,
    codeforces_id TEXT,
    codechef_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (roll_no) REFERENCES students(roll_no) ON DELETE CASCADE
);

-- 8. LeetCode Stats Table
CREATE TABLE leetcode_stats (
    roll_no TEXT PRIMARY KEY,
    weekly_rank INT,
    weekly_problems_solved INT,
    biweekly_rank INT,
    biweekly_problems_solved INT,
    contest_rating INT,
    total_problems_solved INT,
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (roll_no) REFERENCES students(roll_no) ON DELETE CASCADE
);

-- ⚡ Indexes for Platform Joins
CREATE INDEX idx_platforms_roll_no ON student_platforms(roll_no);
CREATE INDEX idx_leetcode_roll_no ON leetcode_stats(roll_no);

-- 9. RPC — Get Students with LeetCode IDs
CREATE OR REPLACE FUNCTION get_students_with_leetcode()
RETURNS TABLE (
    roll_no TEXT,
    name TEXT,
    leetcode_id TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sp.roll_no,
        s.name,
        sp.leetcode_id
    FROM student_platforms sp
    JOIN students s ON s.roll_no = sp.roll_no
    WHERE sp.leetcode_id IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- 10. RPC — LeetCode Analytics for Frontend
CREATE OR REPLACE FUNCTION get_leetcode_analytics()
RETURNS TABLE (
    roll_no TEXT,
    name TEXT,
    department TEXT,
    section TEXT,
    year INT,
    weekly_rank INT,
    weekly_problems_solved INT,
    biweekly_rank INT,
    biweekly_problems_solved INT,
    contest_rating INT,
    total_problems_solved INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.roll_no,
        s.name,
        s.department,
        s.section,
        s.year,
        l.weekly_rank,
        l.weekly_problems_solved,
        l.biweekly_rank,
        l.biweekly_problems_solved,
        l.contest_rating,
        l.total_problems_solved
    FROM students s
    JOIN leetcode_stats l ON s.roll_no = l.roll_no;
END;
$$ LANGUAGE plpgsql;

-- 11. RPC — Platform Department Leaderboard
CREATE OR REPLACE FUNCTION get_platform_department_leaderboard(p_platform TEXT)
RETURNS TABLE (department TEXT, total_score BIGINT) AS $$
BEGIN
    IF p_platform = 'leetcode' THEN
        RETURN QUERY
        SELECT s.department, SUM(l.contest_rating)::BIGINT as total_score
        FROM leetcode_stats l
        JOIN students s ON l.roll_no = s.roll_no
        GROUP BY s.department
        ORDER BY total_score DESC;
    ELSE
        -- Default to HackerRank logic (already exists in get_department_leaderboard)
        RETURN QUERY SELECT * FROM get_department_leaderboard();
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 12. RPC — Get Students who did NOT participate in LeetCode Contest
CREATE OR REPLACE FUNCTION get_leetcode_absent_students(p_contest_type TEXT)
RETURNS TABLE (
    roll_no TEXT,
    name TEXT,
    leetcode_id TEXT,
    department TEXT,
    section TEXT,
    year INT
) AS $$
BEGIN
    IF p_contest_type = 'weekly' THEN
        RETURN QUERY
        SELECT 
            s.roll_no,
            s.name,
            sp.leetcode_id,
            s.department,
            s.section,
            s.year
        FROM students s
        JOIN student_platforms sp ON s.roll_no = sp.roll_no
        LEFT JOIN leetcode_stats l ON s.roll_no = l.roll_no
        WHERE sp.leetcode_id IS NOT NULL 
          AND (l.weekly_rank IS NULL OR l.roll_no IS NULL);
    ELSIF p_contest_type = 'biweekly' THEN
        RETURN QUERY
        SELECT 
            s.roll_no,
            s.name,
            sp.leetcode_id,
            s.department,
            s.section,
            s.year
        FROM students s
        JOIN student_platforms sp ON s.roll_no = sp.roll_no
        LEFT JOIN leetcode_stats l ON s.roll_no = l.roll_no
        WHERE sp.leetcode_id IS NOT NULL 
          AND (l.biweekly_rank IS NULL OR l.roll_no IS NULL);
    END IF;
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
RETURNS TABLE (id UUID, name TEXT, total_score BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.name, SUM(l.score) as total_score
    FROM leaderboard l
    JOIN students s ON l.username = s.hackerrank_username
    GROUP BY s.id, s.name
    ORDER BY total_score DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- 4. Students who did NOT participate
CREATE OR REPLACE FUNCTION get_absent_students(p_contest_name TEXT)
RETURNS TABLE (id UUID, hackerrank_username TEXT, name TEXT, dept TEXT, section TEXT, year INT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.hackerrank_username, s.name, s.department as dept, s.section, s.year
    FROM students s
    WHERE s.hackerrank_username NOT IN (
        SELECT l.username
        FROM leaderboard l
        WHERE l.contest_name = p_contest_name
    );
END;
$$ LANGUAGE plpgsql;

-- 5. All Raw Data for Frontend with Rank
CREATE OR REPLACE FUNCTION get_all_raw_data()
RETURNS TABLE (
    student_id UUID,
    name TEXT,
    username TEXT,
    department TEXT,
    section TEXT,
    year INT,
    contest_name TEXT,
    score INT,
    time_taken INT,
    rank BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id as student_id,
        s.name,
        s.hackerrank_username as username,
        s.department,
        s.section,
        s.year,
        l.contest_name,
        l.score,
        l.time_taken,
        RANK() OVER (PARTITION BY l.contest_name ORDER BY l.score DESC, l.time_taken ASC) as rank
    FROM leaderboard l
    JOIN students s ON l.username = s.hackerrank_username
    ORDER BY l.contest_name, rank;
END;
$$ LANGUAGE plpgsql;

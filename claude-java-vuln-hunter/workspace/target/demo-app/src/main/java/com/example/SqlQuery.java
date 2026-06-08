package com.example;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.sql.SQLException;

/**
 * Deliberately vulnerable SQL query builder. Uses H2 in-memory DB.
 *
 * Jazzer's SQL Injection sanitizer flags executions where attacker input
 * meaningfully changes the parsed SQL structure.
 */
public class SqlQuery {

    private static Connection conn;

    private static synchronized Connection conn() throws SQLException {
        if (conn == null) {
            conn = DriverManager.getConnection("jdbc:h2:mem:demo;DB_CLOSE_DELAY=-1");
            try (Statement s = conn.createStatement()) {
                s.execute("CREATE TABLE IF NOT EXISTS users(id INT, name VARCHAR(64))");
                s.execute("INSERT INTO users VALUES (1, 'alice')");
            }
        }
        return conn;
    }

    public String lookupUser(String userName) throws SQLException {
        // VULN: classic SQL injection via string concatenation
        String sql = "SELECT id FROM users WHERE name = '" + userName + "'";
        try (Statement s = conn().createStatement();
             ResultSet rs = s.executeQuery(sql)) {
            if (rs.next()) {
                return "user " + rs.getInt(1);
            }
            return "not found";
        }
    }
}

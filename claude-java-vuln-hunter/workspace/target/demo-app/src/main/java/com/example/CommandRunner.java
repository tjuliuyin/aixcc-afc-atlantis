package com.example;

import java.io.IOException;

/**
 * Deliberately vulnerable command runner.
 *
 * The "denylist" only blocks one of many separators, and the call uses
 * Runtime.exec(String[]) where the FIRST element is attacker-derived.
 * Jazzer's OS Command Injection sanitizer fires when the first argv element
 * is its sentinel command name.
 */
public class CommandRunner {

    public int runTool(String userCommand) throws IOException, InterruptedException {
        if (userCommand == null || userCommand.isEmpty()) {
            return -1;
        }
        // Only blocks the most obvious separator — many bypasses remain.
        if (userCommand.indexOf(';') >= 0) {
            throw new IllegalArgumentException("nope");
        }
        // VULN: split the user string by whitespace and pass DIRECTLY to exec.
        // Whatever the user puts first becomes the program name.
        String[] argv = userCommand.split("\\s+");
        Process p = Runtime.getRuntime().exec(argv);
        return p.waitFor();
    }
}

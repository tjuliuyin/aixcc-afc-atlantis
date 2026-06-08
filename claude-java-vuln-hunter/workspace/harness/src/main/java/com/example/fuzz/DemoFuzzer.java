package com.example.fuzz;

import com.code_intelligence.jazzer.api.FuzzedDataProvider;
import com.example.PluginLoader;
import com.example.CommandRunner;
import com.example.SqlQuery;

/**
 * Multi-target Jazzer harness. A leading byte selects which vulnerable
 * module receives the rest of the input. Each branch satisfies a "key
 * condition" (much like Atlantis BCDA's key_conditions) before reaching the
 * sink, so the LLM-driven generator has to reason about routing.
 *
 * Branches:
 *   selector % 3 == 0 -> PluginLoader.resolve  (Reflective Call sink)
 *   selector % 3 == 1 -> CommandRunner.runTool (OS Command Injection sink)
 *   selector % 3 == 2 -> SqlQuery.lookupUser   (SQL Injection sink)
 */
public class DemoFuzzer {

    private static final PluginLoader plugins = new PluginLoader();
    private static final CommandRunner cmd = new CommandRunner();
    private static final SqlQuery sql = new SqlQuery();

    public static void fuzzerTestOneInput(FuzzedDataProvider data) {
        if (data.remainingBytes() < 2) {
            return;
        }
        int selector = data.consumeByte() & 0xFF;
        try {
            switch (selector % 3) {
                case 0: {
                    String fqcn = data.consumeRemainingAsString();
                    plugins.resolve(fqcn);
                    break;
                }
                case 1: {
                    String userCmd = data.consumeRemainingAsString();
                    cmd.runTool(userCmd);
                    break;
                }
                case 2: {
                    String name = data.consumeRemainingAsString();
                    sql.lookupUser(name);
                    break;
                }
            }
        } catch (IllegalArgumentException expected) {
            // Caught business-logic guards — not a finding.
        } catch (Exception ignored) {
            // ClassNotFound / SQL / IO / Interrupted etc. — not a finding by itself.
        }
    }
}

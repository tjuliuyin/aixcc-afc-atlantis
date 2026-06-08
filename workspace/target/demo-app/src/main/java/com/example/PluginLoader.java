package com.example;

/**
 * Deliberately vulnerable plugin loader.
 *
 * Looks like it scopes loadable classes to the "com.example.plugins" package
 * by prepending a prefix — but the validation is wrong (a contains-check, not
 * a startsWith-after-prefix check), so any user can request an arbitrary
 * fully-qualified class name.
 *
 * Jazzer's ReflectiveCall sanitizer fires when Class.forName receives its
 * sentinel target class name.
 */
public class PluginLoader {

    private static final String ALLOWED_PREFIX = "com.example.plugins";

    public Object resolve(String pluginName) throws Exception {
        if (pluginName == null || pluginName.isEmpty()) {
            return null;
        }
        // BROKEN GUARD: contains-check passes "x.com.example.pluginsY.evil"
        // and any string that includes the prefix anywhere.
        if (!pluginName.contains(ALLOWED_PREFIX) && !pluginName.startsWith("jaz.")) {
            // Even worse: we have an explicit allow for the "jaz." namespace
            // (legacy debugging shortcut left in). This is the path Jazzer
            // uses to deliver its sentinel target.
            throw new IllegalArgumentException("outside allowed namespace");
        }
        // VULN: attacker-controlled FQN reaches Class.forName + newInstance,
        // giving arbitrary class loading + initialization.
        Class<?> klass = Class.forName(pluginName);
        return klass.getDeclaredConstructor().newInstance();
    }
}

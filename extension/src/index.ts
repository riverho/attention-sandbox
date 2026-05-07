/**
 * Attention Sandbox Extension for Pi
 * 
 * Minimal folder sandbox. Just a stopper + commands.
 * 
 * AGENTS: Read this so you know your boundaries. Work WITH the sandbox,
 * not against it. When you need access outside mapped zones, ask the user
 * to expand the map BEFORE trying to access.
 * 
 * USERS: Type !MAP, !STATUS, or !SANDBOX to manage your boundaries.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import * as yaml from "js-yaml";

// ── Types ──────────────────────────────────────────────────────────────────

type Permission = "allow:rw" | "allow:ro" | "deny" | "ask:rw" | "ask:ro";

interface MapRule {
  path: string;
  perm: Permission;
  note?: string;
}

interface SandboxMap {
  map: Record<string, { perm: Permission; note?: string }>;
}

// ── Path Safety ────────────────────────────────────────────────────────────

function normalizePath(p: string, cwd: string): string {
  p = p.replace(/^~\//, `${process.env.HOME || "/"}/`);
  p = p.replace(/^~$/, process.env.HOME || "/");
  if (!path.isAbsolute(p)) {
    p = path.resolve(cwd, p);
  }
  return path.resolve(p);
}

function isPathInside(root: string, target: string): boolean {
  const rootSep = root.endsWith(path.sep) ? root : root + path.sep;
  const rel = path.relative(rootSep, target);
  return !rel.startsWith("..") && rel !== "";
}

// ── !MAP Engine ────────────────────────────────────────────────────────────

class FolderMap {
  private rules: MapRule[] = [];
  private cwd: string;
  private mapFile: string | null = null;

  constructor(cwd: string) {
    this.cwd = cwd;
  }

  loadFromYaml(filePath: string): boolean {
    try {
      const content = fs.readFileSync(filePath, "utf-8");
      const parsed = yaml.load(content) as SandboxMap;
      if (!parsed || !parsed.map) return false;

      this.rules = Object.entries(parsed.map).map(([rawPath, cfg]) => ({
        path: normalizePath(rawPath, this.cwd),
        perm: cfg.perm,
        note: cfg.note || "",
      }));

      this.rules.sort((a, b) => b.path.length - a.path.length);
      this.mapFile = filePath;
      return true;
    } catch {
      return false;
    }
  }

  check(target: string, operation: "read" | "write" = "read"): MapRule | null {
    const resolved = normalizePath(target, this.cwd);

    for (const rule of this.rules) {
      if (isPathInside(rule.path, resolved) || resolved === rule.path) {
        if (operation === "write" && (rule.perm === "allow:ro" || rule.perm === "ask:ro")) {
          return { path: rule.path, perm: "deny", note: `Write denied: ${rule.note}` };
        }
        return rule;
      }
    }
    return null;
  }

  isMapped(target: string, operation: "read" | "write" = "read"): boolean {
    const rule = this.check(target, operation);
    return rule !== null && rule.perm !== "deny";
  }

  addRule(rawPath: string, perm: Permission, note: string = ""): void {
    const resolved = normalizePath(rawPath, this.cwd);
    // Remove existing rule at same path
    this.rules = this.rules.filter(r => r.path !== resolved);
    this.rules.push({ path: resolved, perm, note });
    this.rules.sort((a, b) => b.path.length - a.path.length);
  }

  removeRule(rawPath: string): boolean {
    const resolved = normalizePath(rawPath, this.cwd);
    const before = this.rules.length;
    this.rules = this.rules.filter(r => r.path !== resolved);
    return this.rules.length < before;
  }

  getMappedPaths(): string[] {
    return this.rules
      .filter(r => r.perm.startsWith("allow") || r.perm.startsWith("ask"))
      .map(r => r.path);
  }

  getAllowPaths(): string[] {
    return this.rules
      .filter(r => r.perm === "allow:rw" || r.perm === "allow:ro")
      .map(r => r.path);
  }

  toSummary(): string {
    const systemNotes = ["Pi system files", "Pi CLI", "Pi user config", "Common CLI tools", "System utilities", "Core system binaries", "Homebrew binaries", "Homebrew packages", "Global node modules"];
    return this.rules
      .filter(r => r.note && !systemNotes.some(sn => r.note?.includes(sn)))
      .map(r => {
        const icon = r.perm.startsWith("allow:rw") ? "🟢" 
          : r.perm.startsWith("allow:ro") ? "🟡"
          : r.perm === "deny" ? "🔴"
          : "🔵";
        return `${icon} ${r.path} -> ${r.perm}${r.note ? ` (${r.note})` : ""}`;
      }).join("\n");
  }

  save(): boolean {
    if (!this.mapFile) return false;
    const mapData: SandboxMap = { map: {} };
    for (const rule of this.rules) {
      mapData.map[rule.path] = { perm: rule.perm, note: rule.note };
    }
    try {
      fs.writeFileSync(this.mapFile, yaml.dump(mapData), "utf-8");
      return true;
    } catch {
      return false;
    }
  }
}

// ── Path Extraction ──────────────────────────────────────────────────────

function extractPaths(toolName: string, args: Record<string, unknown>): Array<{ path: string; op: "read" | "write" }> {
  const paths: Array<{ path: string; op: "read" | "write" }> = [];

  if (toolName === "read" || toolName === "edit") {
    if (typeof args.path === "string") {
      paths.push({ path: args.path, op: toolName === "edit" ? "write" : "read" });
    }
  } else if (toolName === "write") {
    if (typeof args.path === "string") {
      paths.push({ path: args.path, op: "write" });
    }
  } else if (toolName === "bash") {
    const cmd = String(args.command || "");
    const pathMatches = cmd.match(/(?:^|\s)([~./]?\/[^\s;|&<>\"'`]+)/g) || [];
    for (const m of pathMatches) {
      const p = m.trim();
      if (p && !p.startsWith("-") && !p.startsWith("//")) {
        paths.push({ path: p, op: "read" });
      }
    }
  }

  return paths;
}

// ── Error Formatting ───────────────────────────────────────────────────────

function formatMultiStopError(
  toolName: string,
  violations: Array<{ path: string; reason: "outside-map" | "deny"; rule?: MapRule }>,
  map: FolderMap
): string {
  const mapped = map.getAllowPaths();
  const mappedList = mapped.length > 0
    ? mapped.map(p => `  • ${p}`).join("\n")
    : "  (none configured)";

  const outside = violations.filter(v => v.reason === "outside-map");
  const denied = violations.filter(v => v.reason === "deny");

  const lines = [
    "",
    "🔒 SANDBOX STOP",
    "",
    `The agent tried to **${toolName}** on ${violations.length} path(s) outside the sandbox:`,
    ...violations.map(v => {
      if (v.reason === "outside-map") return `  • ${v.path}  (not in map)`;
      return `  • ${v.path}  (denied: ${v.rule?.note || "blocked"})`;
    }),
    "",
    "Currently allowed paths:",
    mappedList,
    "",
  ];

  if (outside.length > 0) {
    if (outside.length === 1) {
      lines.push("To expand the sandbox:");
      lines.push(`  !MAP ${outside[0].path} -> allow:rw`);
      lines.push("");
      lines.push(`Or ask: "Should I add ${outside[0].path} to the sandbox?"`);
    } else {
      lines.push("To expand the sandbox, add the paths you want to allow:");
      for (const v of outside) {
        lines.push(`  !MAP ${v.path} -> allow:rw`);
      }
      lines.push("");
      const allPaths = outside.map(v => v.path).join(", ");
      lines.push(`Or ask: "Should I add these paths to the sandbox: ${allPaths}?"`);
    }
  }

  if (denied.length > 0) {
    lines.push("");
    lines.push("⚠️ Some paths are permanently denied and cannot be added:");
    for (const v of denied) {
      lines.push(`  • ${v.path} (${v.rule?.note || "deny rule"})`);
    }
  }

  lines.push("");
  return lines.join("\n");
}

function formatAgentContext(map: FolderMap): string {
  const mapped = map.getAllowPaths();
  const mappedList = mapped.length > 0 ? mapped.join("\n  ") : "(none - working directory only)";

  return [
    "",
    "📋 SANDBOX BOUNDARIES — You are operating inside a !MAP sandbox.",
    "",
    "You may freely access these paths:",
    `  ${mappedList}`,
    "",
    "Rules:",
    "  1. Before accessing paths outside the map, ASK the user to expand.",
    "  2. Use !MAP <path> -> allow:rw to add paths (user must confirm).",
    "  3. If you hit a sandbox stop, adapt your plan — do not retry blindly.",
    "",
    "Example proactive message:",
    '  "I need to access ~/Desktop/ to complete this. Should I add it to the sandbox?"',
    "",
  ].join("\n");
}

// ── Always-Allowed System Paths ───────────────────────────────────────────
// These are essential for Pi to function and common agent workflows.
// They bypass normal map checking and are always permitted.

const ALWAYS_ALLOW_PATHS: Array<{ path: string; perm: "allow:rw" | "allow:ro"; note: string }> = [
  // Pi's own installation and config
  { path: "/usr/local/lib/node_modules/@mariozechner/pi-coding-agent", perm: "allow:ro", note: "Pi system files" },
  { path: "/usr/local/bin/pi", perm: "allow:ro", note: "Pi CLI" },
  
  // User's global Pi config
  { path: "~/.pi", perm: "allow:rw", note: "Pi user config and extensions" },
  
  // Common system utilities agents need
  { path: "/usr/local/bin", perm: "allow:ro", note: "Common CLI tools" },
  { path: "/usr/bin", perm: "allow:ro", note: "System utilities" },
  { path: "/bin", perm: "allow:ro", note: "Core system binaries" },
  
  // Homebrew on macOS (common tool source)
  { path: "/opt/homebrew/bin", perm: "allow:ro", note: "Homebrew binaries" },
  { path: "/opt/homebrew/opt", perm: "allow:ro", note: "Homebrew packages" },
  
  // Node/npm binaries (agents often run npm scripts)
  { path: "/usr/local/lib/node_modules", perm: "allow:ro", note: "Global node modules" },
];

function addAlwaysAllowedPaths(map: FolderMap, cwd: string): void {
  for (const { path: rawPath, perm, note } of ALWAYS_ALLOW_PATHS) {
    const resolved = normalizePath(rawPath, cwd);
    // Only add if the path actually exists on this system
    if (fs.existsSync(resolved)) {
      // Use addRule but mark as system so it doesn't show in user-facing summaries
      map.addRule(resolved, perm, note);
    }
  }
}

function detectProjectRoot(startDir: string): string | null {
  let current = startDir;
  const markers = [".git", ".wenmei", "package.json", "pyproject.toml", "Cargo.toml", "go.mod"];
  
  while (current !== path.dirname(current)) {
    for (const marker of markers) {
      if (fs.existsSync(path.join(current, marker))) {
        return current;
      }
    }
    current = path.dirname(current);
  }
  return null;
}

function autoInitMap(cwd: string, map: FolderMap): { created: boolean; projectRoot: string | null } {
  const projectRoot = detectProjectRoot(cwd);
  const root = projectRoot || cwd;
  
  // Project root = allow:rw
  map.addRule(root, "allow:rw", projectRoot ? "Project root (auto-detected)" : "Current directory");
  
  // Common project subdirectories
  if (projectRoot) {
    // Dependencies: deny by default
    const depsDirs = ["node_modules", ".venv", "venv", "vendor", "target/debug", "target/release"];
    for (const d of depsDirs) {
      const depPath = path.join(root, d);
      if (fs.existsSync(depPath)) {
        map.addRule(depPath, "deny", "Dependencies — do not modify");
      }
    }
    
    // .git: read-only
    const gitPath = path.join(root, ".git");
    if (fs.existsSync(gitPath)) {
      map.addRule(gitPath, "allow:ro", "Git history read-only");
    }
  }
  
  // Parent workspace: read-only (if different from root)
  const parent = path.dirname(root);
  if (parent !== root && parent !== "/") {
    map.addRule(parent, "allow:ro", "Parent workspace read-only");
  }
  
  // Global deny
  map.addRule("/", "deny", "Outside sandbox (default)");
  
  // Save to .pi/sandbox-map.yaml
  const piDir = path.join(cwd, ".pi");
  const mapFile = path.join(piDir, "sandbox-map.yaml");
  
  try {
    fs.mkdirSync(piDir, { recursive: true });
    const mapData = { map: {} as Record<string, { perm: Permission; note?: string }> };
    for (const rule of (map as any).rules) {
      mapData.map[rule.path] = { perm: rule.perm, note: rule.note };
    }
    fs.writeFileSync(mapFile, yaml.dump(mapData), "utf-8");
    (map as any).mapFile = mapFile;
    return { created: true, projectRoot };
  } catch {
    return { created: false, projectRoot };
  }
}

function createSandboxExtension(pi: any) {
  const cwd = pi.cwd || process.cwd();
  const map = new FolderMap(cwd);

  // ── Load Map ───────────────────────────────────────────────────────────
  const mapPaths = [
    path.join(cwd, ".pi", "sandbox-map.yaml"),
    path.join(cwd, ".agents", "sandbox-map.yaml"),
    path.join(cwd, "sandbox-map.yaml"),
    path.join(process.env.HOME || "~", ".pi", "agent", "sandbox-map.yaml"),
  ];

  let mapLoaded = false;
  let autoCreated = false;
  let projectRoot: string | null = null;

  for (const mp of mapPaths) {
    if (map.loadFromYaml(mp)) {
      mapLoaded = true;
      break;
    }
  }

  if (!mapLoaded) {
    // Auto-init for new folders without metadata
    const init = autoInitMap(cwd, map);
    autoCreated = init.created;
    projectRoot = init.projectRoot;
  }

  const mode = mapLoaded ? "loaded from file" : autoCreated ? "auto-created" : "default";
  
  // Add always-allowed system paths (Pi, common tools)
  addAlwaysAllowedPaths(map, cwd);
  
  // Build startup notification
  const startupLines = [
    `[sandbox] Map ${mode}`,
  ];
  if (projectRoot && projectRoot !== cwd) {
    startupLines.push(`[sandbox] Project root detected: ${projectRoot}`);
  }
  if (autoCreated) {
    startupLines.push(`[sandbox] Created .pi/sandbox-map.yaml — edit it or use !MAP to customize`);
  }
  startupLines.push(map.toSummary());
  
  const startupMsg = startupLines.join("\n");
  
  // Log to terminal (for debugging)
  console.log(startupMsg);
  
  // Send to Pi chat UI so user actually sees it
  pi.sendMessage({
    type: "text",
    content: "🛡️ **Attention Sandbox**\n```\n" + startupMsg + "\n```",
  });

  // ── Inject Agent Context ──────────────────────────────────────────────
  // Tell the agent about sandbox boundaries at startup
  const agentContext = formatAgentContext(map);
  
  // Pi extensions can augment system prompt via pi.sendMessage with type "system"
  // or by emitting a context file event. We'll use the simplest approach:
  // prepend to the first user-visible message or inject via event.
  if (pi.injectContext) {
    pi.injectContext(agentContext);
  }

  // ── Command Handlers ────────────────────────────────────────────────────
  pi.onCommand("!MAP", (args: string) => {
    // Parse: !MAP /path -> allow:rw
    const match = args.match(/^(.+?)\s*->\s*(\S+)(?:\s+#\s*(.*))?$/);
    if (!match) {
      pi.sendMessage({
        type: "text",
        content: "Usage: !MAP /path -> allow:rw|allow:ro|deny|ask:rw|ask:ro\nExample: !MAP ~/Desktop -> allow:rw",
      });
      return;
    }

    const [, rawPath, perm, note] = match;
    if (!["allow:rw", "allow:ro", "deny", "ask:rw", "ask:ro"].includes(perm)) {
      pi.sendMessage({
        type: "text",
        content: `Invalid permission: ${perm}. Use allow:rw, allow:ro, deny, ask:rw, or ask:ro.`,
      });
      return;
    }

    map.addRule(rawPath.trim(), perm as Permission, note || "Added via !MAP");
    
    // Try to persist
    const saved = map.save();
    
    pi.sendMessage({
      type: "text",
      content: `✅ Mapped: ${normalizePath(rawPath.trim(), cwd)} -> ${perm}${saved ? " (saved)" : " (session only)"}`,
    });
    
    // Update agent context
    if (pi.injectContext) {
      pi.injectContext(formatAgentContext(map));
    }
  });

  pi.onCommand("!UNMAP", (args: string) => {
    const removed = map.removeRule(args.trim());
    if (removed) {
      map.save();
      pi.sendMessage({
        type: "text",
        content: `🗑️ Removed map for ${normalizePath(args.trim(), cwd)}`,
      });
    } else {
      pi.sendMessage({
        type: "text",
        content: `❌ No map found for ${args.trim()}`,
      });
    }
  });

  pi.onCommand("!STATUS", () => {
    pi.sendMessage({
      type: "text",
      content: `📋 Current Sandbox Map:\n\n${map.toSummary()}`,
    });
  });

  pi.onCommand("!SANDBOX", () => {
    pi.sendMessage({
      type: "text",
      content: [
        "🛡️ Attention Sandbox Commands:",
        "",
        "  !MAP <path> -> <perm>  — Add or update a path rule",
        "  !UNMAP <path>          — Remove a path rule",
        "  !STATUS                — Show current map",
        "  !SANDBOX               — Show this help",
        "",
        "Permissions: allow:rw, allow:ro, deny, ask:rw, ask:ro",
        "",
        "Examples:",
        "  !MAP ~/Desktop -> allow:rw",
        "  !MAP ~/.ssh -> deny",
        "  !MAP /tmp -> ask:rw",
        "  !UNMAP ~/Desktop",
      ].join("\n"),
    });
  });

  // ── Tool Interception ───────────────────────────────────────────────────
  pi.on("tool_execution_start", (event: any) => {
    const toolName = event.toolName;
    const args = event.toolArgs || {};

    const paths = extractPaths(toolName, args);
    if (paths.length === 0) return;

    // First pass: check ALL paths and collect violations
    const violations: Array<{ path: string; reason: "outside-map" | "deny"; rule?: MapRule }> = [];

    for (const { path: p, op } of paths) {
      const rule = map.check(p, op);
      if (!rule) {
        violations.push({ path: p, reason: "outside-map" });
      } else if (rule.perm === "deny") {
        violations.push({ path: p, reason: "deny", rule });
      }
      // allow:* and ask:* pass silently
    }

    if (violations.length > 0) {
      // Block and show summary of ALL violations
      const errorMsg = formatMultiStopError(toolName, violations, map);

      pi.sendMessage({
        type: "tool_result",
        toolCallId: event.toolCallId,
        content: errorMsg,
        isError: true,
      });

      // Notification with summary
      const outsideCount = violations.filter(v => v.reason === "outside-map").length;
      const denyCount = violations.filter(v => v.reason === "deny").length;
      const parts: string[] = [];
      if (outsideCount > 0) parts.push(`${outsideCount} outside map`);
      if (denyCount > 0) parts.push(`${denyCount} denied`);

      const notifyMsg = `🔒 **Sandbox Stop**: agent tried **${toolName}** — ${parts.join(", ")}`;

      if (pi.notify) {
        pi.notify(`🔒 Stopped: ${toolName} (${violations.length} path${violations.length > 1 ? "s" : ""})`);
      }

      pi.sendMessage({
        type: "text",
        content: notifyMsg,
      });

      // Log to .wenmei/journal
      try {
        const journalDir = path.join(cwd, ".wenmei");
        if (fs.existsSync(journalDir)) {
          const journalPath = path.join(journalDir, "journal.jsonl");
          for (const v of violations) {
            const entry = JSON.stringify({
              ts: new Date().toISOString(),
              kind: "sandbox.stop",
              tool: toolName,
              path: v.path,
              reason: v.reason,
            }) + "\n";
            fs.appendFileSync(journalPath, entry);
          }
        }
      } catch {
        // Best effort
      }

      return;
    }

    // All paths allowed — proceed silently
    // ask:* paths were already logged above, now we pass through
  });
}

export default createSandboxExtension;
if (typeof module !== "undefined" && module.exports) {
  module.exports = createSandboxExtension;
}

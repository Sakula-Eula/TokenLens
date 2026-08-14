"use strict";

const fs = require("node:fs");
const path = require("node:path");

class UsageStore {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.usagePath = path.join(dataDir, "usage.jsonl");
    this.configPath = path.join(dataDir, "config.json");
    fs.mkdirSync(dataDir, { recursive: true });
  }

  add(record) {
    fs.appendFileSync(this.usagePath, `${JSON.stringify(record)}\n`, "utf8");
  }

  all() {
    if (!fs.existsSync(this.usagePath)) return [];
    return fs.readFileSync(this.usagePath, "utf8").split("\n").filter(Boolean).flatMap((line) => {
      try { return [JSON.parse(line)]; } catch { return []; }
    });
  }

  getConfig() {
    if (!fs.existsSync(this.configPath)) return { monthlyBudgetUsd: null };
    try {
      const config = JSON.parse(fs.readFileSync(this.configPath, "utf8"));
      return { monthlyBudgetUsd: Number.isFinite(config.monthlyBudgetUsd) ? config.monthlyBudgetUsd : null };
    } catch {
      return { monthlyBudgetUsd: null };
    }
  }

  setConfig(config) {
    const monthlyBudgetUsd = config.monthlyBudgetUsd === null ? null : Number(config.monthlyBudgetUsd);
    if (monthlyBudgetUsd !== null && (!Number.isFinite(monthlyBudgetUsd) || monthlyBudgetUsd < 0)) {
      throw new Error("月度预算必须是大于或等于 0 的数字");
    }
    fs.writeFileSync(this.configPath, JSON.stringify({ monthlyBudgetUsd }, null, 2), "utf8");
    return { monthlyBudgetUsd };
  }
}

module.exports = { UsageStore };


import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const siteRoot = path.resolve(import.meta.dirname, "..");
const packageRoot = path.resolve(siteRoot, "..");
const outputDir = path.join(packageRoot, "output");
const targetDir = path.join(siteRoot, "src", "content", "daily");
const dailyFilename = /^\d{4}-\d{2}-\d{2}\.md$/;

function splitFrontmatter(markdown) {
  if (!markdown.startsWith("---\n")) {
    return { frontmatter: "", body: markdown.trimStart() };
  }

  const end = markdown.indexOf("\n---\n", 4);
  if (end === -1) {
    return { frontmatter: "", body: markdown.trimStart() };
  }

  return {
    frontmatter: markdown.slice(4, end).trim(),
    body: markdown.slice(end + 5).trimStart(),
  };
}

function parseFrontmatter(frontmatter) {
  const data = {};
  for (const line of frontmatter.split("\n")) {
    const separator = line.indexOf(":");
    if (separator === -1) {
      continue;
    }
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (key) {
      data[key] = value;
    }
  }
  return data;
}

function buildDocument(date, data, body) {
  const source = data.source ?? "Hacker News, IndieWeb";
  const title = `Auto Matome Daily Roundup ${date}`;
  const description = `HN と IndieWeb から収集した日次キュレーション (${date})`;

  return `---
title: ${title}
description: ${description}
date: ${date}
source: ${source}
---

${body.trim()}
`;
}

async function main() {
  await mkdir(targetDir, { recursive: true });

  for (const existing of await readdir(targetDir)) {
    if (existing.endsWith(".md")) {
      await rm(path.join(targetDir, existing));
    }
  }

  const files = (await readdir(outputDir))
    .filter((file) => dailyFilename.test(file))
    .sort();

  for (const file of files) {
    const date = file.replace(/\.md$/, "");
    const inputPath = path.join(outputDir, file);
    const outputPath = path.join(targetDir, file);
    const raw = await readFile(inputPath, "utf8");
    const { frontmatter, body } = splitFrontmatter(raw);
    const data = parseFrontmatter(frontmatter);
    await writeFile(outputPath, buildDocument(date, data, body), "utf8");
  }

  process.stdout.write(`Synced ${files.length} daily files to ${targetDir}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exitCode = 1;
});

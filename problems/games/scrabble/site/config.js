// Everything you might want to change lives here. app.js reads only from this.
window.SITE = {
  // --- Identity and links ---
  SITE_NAME: "Rackoon",                       // small text wordmark and share-text name; "" shows nothing
  SITE_URL: "https://example.com",            // production URL: share text, and the only host analytics load on
  BLOG_URL: "https://yash-sri.xyz",
  STORY_URL: "https://yash-sri.xyz/blog/scrabble_cadence", // "the long story" link on About
  X_URL: "https://x.com/Yaaaaaashhh",
  GITHUB_URL: "https://github.com/yash-srivastava19",

  // --- Game rules ---
  TRIES: 3,                                   // valid tries per puzzle
  BEST_TOLERANCE: 0.05,                       // plays within this much value of the best also count as best
  TOP_PLAYS: 5,                               // rows in the "Top plays" table (your tries are added if lower)

  // --- Feedback after a try (value points) ---
  KEPT_FINE_MARGIN: 1,                        // your kept tiles within this of the best's count as "fine"
  WORTH_ROUNDING: 0.5,                        // kept-tile worth smaller than this either way shows as neutral

  // --- Share text: one mark per try, by % of the best play's value ---
  SHARE_BEST_MARK: "■",                       // the try that found the best play
  SHARE_MARKS: "▁▂▃▄▅▆▇",                      // low to high; 0–100% is split evenly across them

  // --- Random practice ---
  PRACTICE_POOL_SIZE: 0,                      // practice puzzles to draw from; 0 means all in puzzles/practice/index.json
  PRACTICE_AVOID_REPEATS: true,               // skip ones this browser has played until all are played

  // --- Calendar ---
  ROLLOVER_TIMEZONE: "local",                 // "local" (each player's midnight) or an IANA zone like "UTC"
  ROLLOVER_HOUR: 0,                           // hour of day the new puzzle appears in that zone
  ARCHIVE_DAYS: 0,                            // how many past days the archive lists; 0 means all

  // --- Storage and flags ---
  STORAGE_KEY: "bestplay:v1",                 // localStorage key for results, stats, theme. Never change it: players lose progress
  LEGACY_STORAGE_KEYS: ["dailytiles:v1", "rackoon:v1"], // older keys, merged into STORAGE_KEY once and left alone
  TOAST_MS: 2600,                             // how long the "Copied" note stays
  ANALYTICS: true,                            // Vercel Web Analytics + Speed Insights, only on SITE_URL's host

  // --- About page copy (HTML allowed; {story} becomes the long-story link) ---
  ABOUT: [
    // Yash: replace this first paragraph with your own words.
    "I like Scrabble because it's where luck, vocabulary and judgment meet. Most of the skill isn't knowing big words. It's deciding what to keep for later.",
    "The bot behind these puzzles came out of exploring how programs improve themselves: self-play, simulation, and measuring against the best bots around. The {story} is on my blog.",
    "This is just for fun. One puzzle a day. No accounts, no cookies. Anonymous visit counts only.",
  ],
  ABOUT_FINE: "Not affiliated with or endorsed by Scrabble's owners.",

  // --- Learn more (end of How to play) ---
  LEARN: [
    { name: "Woogles", url: "https://woogles.io", note: "Play the crossword board game online, free, against people or bots." },
    { name: "Zyzzyva", url: "https://www.scrabbleplayers.org/w/NASPA_Zyzzyva", note: "Word study software tournament players use: two-letter words, anagrams, quizzes." },
    { name: "Aerolith", url: "https://aerolith.org", note: "Timed anagram drills to find seven-letter plays faster." },
    { name: "Cross-tables", url: "https://www.cross-tables.com", note: "Tournament results, ratings and annotated games from top players." },
    { name: "NASPA rules", url: "https://www.scrabbleplayers.org/w/Rules", note: "The full tournament rules, if you want every detail." },
  ],
};

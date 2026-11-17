require("dotenv").config();
require("@nomicfoundation/hardhat-toolbox");
const { subtask } = require("hardhat/config");
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require("hardhat/builtin-tasks/task-names");

// Use the solc bundled in node_modules (solc-js) so compiling never needs to download a binary.
// Slower than the native compiler but works offline and behind restrictive networks.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD, async (args, hre, runSuper) => {
  if (args.solcVersion === "0.8.24") {
    const solc = require("solc");
    return {
      compilerPath: require.resolve("solc/soljson.js"),
      isSolcJs: true,
      version: args.solcVersion,
      longVersion: solc.version(),
    };
  }
  return runSuper();
});

// Secrets come from the environment only. Never commit a key.
const { DEPLOYER_KEY, BASE_SEPOLIA_RPC } = process.env;

// Fail with a readable message instead of Hardhat's generic "private key too short".
if (DEPLOYER_KEY && !/^(0x)?[0-9a-fA-F]{64}$/.test(DEPLOYER_KEY)) {
  throw new Error(
    "DEPLOYER_KEY must be a private key: 64 hex characters (optionally starting with 0x). " +
      "A wallet address (40 hex characters) or a placeholder will not work."
  );
}

module.exports = {
  solidity: { version: "0.8.24", settings: { optimizer: { enabled: true, runs: 200 } } },
  networks: {
    baseSepolia: {
      url: BASE_SEPOLIA_RPC || "https://sepolia.base.org",
      chainId: 84532,
      accounts: DEPLOYER_KEY ? [DEPLOYER_KEY] : [],
    },
  },
};

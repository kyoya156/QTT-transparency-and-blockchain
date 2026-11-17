// npx hardhat run scripts/deploy.js                       (in-process test chain, nothing persists)
// DEPLOYER_KEY=0x... RECORDER_ADDRESS=0x... npx hardhat run scripts/deploy.js --network baseSepolia
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

async function main() {
  const recorderEnv = (process.env.RECORDER_ADDRESS || "").trim();
  if (recorderEnv && !ethers.isAddress(recorderEnv)) {
    throw new Error(`RECORDER_ADDRESS is not a valid address: ${JSON.stringify(recorderEnv)}. ` +
      "Expected 0x followed by 40 hex characters, with no quotes or spaces.");
  }
  const [deployer] = await ethers.getSigners();
  console.log("network:", network.name, "| deployer:", deployer.address);

  const ledger = await (await ethers.getContractFactory("TransparencyLedger")).deploy(deployer.address);
  await ledger.waitForDeployment();
  const address = await ledger.getAddress();
  console.log("TransparencyLedger:", address);

  const recorder = recorderEnv ? ethers.getAddress(recorderEnv) : null;
  if (network.name !== "hardhat") {
    const dir = path.join(__dirname, "..", "deployments");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, `${network.name}.json`),
      JSON.stringify({ address, deployer: deployer.address, recorder,
                       block: await ethers.provider.getBlockNumber() }, null, 2));
  }

  if (recorder) {
    await (await ledger.grantRole(await ledger.RECORDER_ROLE(), recorder)).wait();
    console.log("recorder role granted to", recorder);
  } else {
    console.log("no RECORDER_ADDRESS set: run scripts/grant-recorder.js before use");
  }
}

main().catch((e) => { console.error(e); process.exit(1); });

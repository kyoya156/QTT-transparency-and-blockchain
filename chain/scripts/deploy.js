// npx hardhat run scripts/deploy.js                       (in-process test chain, nothing persists)
// DEPLOYER_KEY=0x... RECORDER_ADDRESS=0x... npx hardhat run scripts/deploy.js --network baseSepolia
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("network:", network.name, "| deployer:", deployer.address);

  const ledger = await (await ethers.getContractFactory("TransparencyLedger")).deploy(deployer.address);
  await ledger.waitForDeployment();
  const address = await ledger.getAddress();
  console.log("TransparencyLedger:", address);

  const recorder = process.env.RECORDER_ADDRESS;
  if (recorder) {
    await (await ledger.grantRole(await ledger.RECORDER_ROLE(), recorder)).wait();
    console.log("recorder role granted to", recorder);
  } else {
    console.log("no RECORDER_ADDRESS set: grant RECORDER_ROLE to the listener's address before use");
  }

  if (network.name !== "hardhat") {
    const dir = path.join(__dirname, "..", "deployments");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, `${network.name}.json`),
      JSON.stringify({ address, deployer: deployer.address, recorder: recorder || null,
                       block: (await ethers.provider.getBlockNumber()) }, null, 2));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });

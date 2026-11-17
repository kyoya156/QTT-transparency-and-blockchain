// Gives RECORDER_ROLE to the listener on an already deployed ledger. Safe to run twice.
//   .env needs: DEPLOYER_KEY (the admin), CONTRACT_ADDRESS, RECORDER_ADDRESS
//   npx hardhat run scripts/grant-recorder.js --network baseSepolia
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

function need(name) {
  const v = (process.env[name] || "").trim();
  if (!ethers.isAddress(v)) {
    throw new Error(`${name} is not a valid address: ${JSON.stringify(v)}. ` +
      "Expected 0x followed by 40 hex characters, with no quotes or spaces.");
  }
  return ethers.getAddress(v);
}

async function main() {
  const contract = need("CONTRACT_ADDRESS");
  const recorder = need("RECORDER_ADDRESS");
  const [admin] = await ethers.getSigners();
  const ledger = await ethers.getContractAt("TransparencyLedger", contract, admin);
  const role = await ledger.RECORDER_ROLE();

  if (await ledger.hasRole(role, recorder)) {
    console.log("already a recorder:", recorder);
  } else {
    await (await ledger.grantRole(role, recorder)).wait();
    console.log("recorder role granted to", recorder);
  }
  console.log("hasRole check:", await ledger.hasRole(role, recorder));

  if (network.name !== "hardhat") {
    const dir = path.join(__dirname, "..", "deployments");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, `${network.name}.json`),
      JSON.stringify({ address: contract, deployer: admin.address, recorder,
                       block: await ethers.provider.getBlockNumber() }, null, 2));
  }
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });

const { expect } = require("chai");
const { ethers } = require("hardhat");

const h = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));

describe("TransparencyLedger", () => {
  let ledger, admin, recorder, stranger, RECORDER;

  beforeEach(async () => {
    [admin, recorder, stranger] = await ethers.getSigners();
    ledger = await (await ethers.getContractFactory("TransparencyLedger")).deploy(admin.address);
    RECORDER = await ledger.RECORDER_ROLE();
    await ledger.grantRole(RECORDER, recorder.address);
  });

  it("records income and emits an event", async () => {
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1")))
      .to.emit(ledger, "Income").withArgs(h("tx1"), h("leaf1"));
    expect(await ledger.verify(h("tx1"), h("leaf1"))).to.equal(true);
  });

  it("records expense with its own event", async () => {
    await expect(ledger.connect(recorder).recordExpense(h("tx2"), h("leaf2")))
      .to.emit(ledger, "Expense").withArgs(h("tx2"), h("leaf2"));
  });

  it("rejects a repeated refId (webhook retry), even with a different leaf", async () => {
    await ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"));
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("other")))
      .to.be.revertedWithCustomError(ledger, "AlreadyRecorded");
    await expect(ledger.connect(recorder).recordExpense(h("tx1"), h("leaf1")))
      .to.be.revertedWithCustomError(ledger, "AlreadyRecorded");
  });

  it("verify fails for a wrong leaf or an unknown refId", async () => {
    await ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"));
    expect(await ledger.verify(h("tx1"), h("tampered"))).to.equal(false);
    expect(await ledger.verify(h("nope"), h("leaf1"))).to.equal(false);
  });

  it("only a recorder can write", async () => {
    await expect(ledger.connect(stranger).recordIncome(h("tx1"), h("leaf1"))).to.be.reverted;
    await expect(ledger.connect(admin).recordIncome(h("tx1"), h("leaf1"))).to.be.reverted;
    await expect(ledger.connect(stranger).anchorBatch(20261117, h("r"), 5)).to.be.reverted;
  });

  it("only the admin can grant or revoke recorders", async () => {
    await expect(ledger.connect(stranger).grantRole(RECORDER, stranger.address)).to.be.reverted;
    await ledger.revokeRole(RECORDER, recorder.address);
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"))).to.be.reverted;
  });

  it("anchors a day once and refuses a second root for the same day", async () => {
    await expect(ledger.connect(recorder).anchorBatch(20261117, h("root"), 25))
      .to.emit(ledger, "BatchAnchored").withArgs(20261117, h("root"), 25);
    await expect(ledger.connect(recorder).anchorBatch(20261117, h("root2"), 25))
      .to.be.revertedWithCustomError(ledger, "DayAlreadyAnchored");
    const b = await ledger.batches(20261117);
    expect(b.root).to.equal(h("root"));
  });

  it("rejects zero values", async () => {
    const z = ethers.ZeroHash;
    await expect(ledger.connect(recorder).recordIncome(z, h("l"))).to.be.revertedWithCustomError(ledger, "EmptyValue");
    await expect(ledger.connect(recorder).anchorBatch(20261117, z, 1)).to.be.revertedWithCustomError(ledger, "EmptyValue");
    await expect(ledger.connect(recorder).anchorBatch(20261117, h("r"), 0)).to.be.revertedWithCustomError(ledger, "EmptyValue");
  });

  it("pause stops writes but not reads; unpause resumes", async () => {
    await ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"));
    await ledger.pause();
    await expect(ledger.connect(recorder).recordIncome(h("tx2"), h("l2"))).to.be.revertedWithCustomError(ledger, "EnforcedPause");
    expect(await ledger.verify(h("tx1"), h("leaf1"))).to.equal(true);
    await expect(ledger.connect(stranger).pause()).to.be.reverted;
    await ledger.unpause();
    await ledger.connect(recorder).recordIncome(h("tx2"), h("l2"));
  });
});

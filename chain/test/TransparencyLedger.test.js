const { expect } = require("chai");
const { ethers } = require("hardhat");

const h = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));

describe("TransparencyLedger v3 (hash only)", () => {
  let ledger, admin, recorder, stranger, RECORDER;

  beforeEach(async () => {
    [admin, recorder, stranger] = await ethers.getSigners();
    ledger = await (await ethers.getContractFactory("TransparencyLedger")).deploy(admin.address);
    RECORDER = await ledger.RECORDER_ROLE();
    await ledger.grantRole(RECORDER, recorder.address);
  });

  it("records only refId and leaf, and emits them", async () => {
    await expect(ledger.connect(recorder).record(h("tx1"), h("leaf1")))
      .to.emit(ledger, "Recorded").withArgs(h("tx1"), h("leaf1"));
    expect(await ledger.verify(h("tx1"), h("leaf1"))).to.equal(true);
    const e = await ledger.entries(h("tx1"));
    expect(e.leaf).to.equal(h("leaf1"));
    expect(e.recordedAt).to.be.greaterThan(0n);
  });

  it("stores no readable record fields", async () => {
    const names = ledger.interface.fragments.map((f) => f.name).filter(Boolean);
    for (const old of ["recordIncome", "recordExpense", "Income", "Expense"]) {
      expect(names).to.not.include(old);
    }
    const entryOutputs = ledger.interface.getFunction("entries").outputs.map((o) => o.name);
    expect(entryOutputs).to.deep.equal(["leaf", "recordedAt"]);
  });

  it("rejects a repeated refId (webhook retry), even with a different leaf", async () => {
    await ledger.connect(recorder).record(h("tx1"), h("leaf1"));
    await expect(ledger.connect(recorder).record(h("tx1"), h("other")))
      .to.be.revertedWithCustomError(ledger, "AlreadyRecorded");
  });

  it("verify fails for a wrong leaf or an unknown refId", async () => {
    await ledger.connect(recorder).record(h("tx1"), h("leaf1"));
    expect(await ledger.verify(h("tx1"), h("tampered"))).to.equal(false);
    expect(await ledger.verify(h("nope"), h("leaf1"))).to.equal(false);
  });

  it("only a recorder can write", async () => {
    await expect(ledger.connect(stranger).record(h("tx1"), h("leaf1"))).to.be.reverted;
    await expect(ledger.connect(admin).record(h("tx1"), h("leaf1"))).to.be.reverted;
    await expect(ledger.connect(stranger).anchorBatch(20261117, h("r"), 5)).to.be.reverted;
  });

  it("only the admin can grant or revoke recorders", async () => {
    await expect(ledger.connect(stranger).grantRole(RECORDER, stranger.address)).to.be.reverted;
    await ledger.revokeRole(RECORDER, recorder.address);
    await expect(ledger.connect(recorder).record(h("tx1"), h("leaf1"))).to.be.reverted;
  });

  it("anchors a day once and refuses a second root for the same day", async () => {
    await expect(ledger.connect(recorder).anchorBatch(20261117, h("root"), 25))
      .to.emit(ledger, "BatchAnchored").withArgs(20261117, h("root"), 25);
    await expect(ledger.connect(recorder).anchorBatch(20261117, h("root2"), 25))
      .to.be.revertedWithCustomError(ledger, "DayAlreadyAnchored");
    expect((await ledger.batches(20261117)).root).to.equal(h("root"));
  });

  it("rejects zero or empty values", async () => {
    const z = ethers.ZeroHash;
    const r = ledger.connect(recorder);
    const calls = [
      () => r.record(z, h("l")),
      () => r.record(h("a"), z),
      () => r.anchorBatch(20261117, z, 1),
      () => r.anchorBatch(20261117, h("r"), 0),
    ];
    for (const call of calls) {
      await expect(call()).to.be.revertedWithCustomError(ledger, "EmptyValue");
    }
  });

  it("pause stops writes but not reads; unpause resumes", async () => {
    await ledger.connect(recorder).record(h("tx1"), h("leaf1"));
    await ledger.pause();
    await expect(ledger.connect(recorder).record(h("tx2"), h("l2")))
      .to.be.revertedWithCustomError(ledger, "EnforcedPause");
    expect(await ledger.verify(h("tx1"), h("leaf1"))).to.equal(true);
    await expect(ledger.connect(stranger).pause()).to.be.reverted;
    await ledger.unpause();
    await ledger.connect(recorder).record(h("tx2"), h("l2"));
  });
});

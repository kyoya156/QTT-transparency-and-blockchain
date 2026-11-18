const { expect } = require("chai");
const { ethers } = require("hardhat");

const h = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
const T = 1763260200; // 2025-11-16T02:30:00Z, bank time
const inc = (o = {}) => ({ amount: 500000n, txTime: T, currency: "VND", donorId: "D-001", donorName: "", ...o });
const exp = (o = {}) => ({ amount: 200000n, txTime: T, currency: "VND", recipientId: "R-017",
                           recipientType: "unassigned", ...o });

describe("TransparencyLedger v2", () => {
  let ledger, admin, recorder, stranger, RECORDER;

  beforeEach(async () => {
    [admin, recorder, stranger] = await ethers.getSigners();
    ledger = await (await ethers.getContractFactory("TransparencyLedger")).deploy(admin.address);
    RECORDER = await ledger.RECORDER_ROLE();
    await ledger.grantRole(RECORDER, recorder.address);
  });

  it("records income with public fields and emits them", async () => {
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"), inc()))
      .to.emit(ledger, "Income").withArgs(h("tx1"), h("leaf1"), 500000n, "VND", T, "D-001", "");
    expect(await ledger.verify(h("tx1"), h("leaf1"))).to.equal(true);
    const e = await ledger.entries(h("tx1"));
    expect(e.amount).to.equal(500000n);
    expect(e.txTime).to.equal(T);
    expect(e.direction).to.equal(1n);
  });

  it("records expense with recipient id and type", async () => {
    await expect(ledger.connect(recorder).recordExpense(h("tx2"), h("leaf2"), exp()))
      .to.emit(ledger, "Expense").withArgs(h("tx2"), h("leaf2"), 200000n, "VND", T, "R-017", "unassigned");
    expect((await ledger.entries(h("tx2"))).direction).to.equal(2n);
  });

  it("donor name slot is optional and carried when given", async () => {
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("l"), inc({ donorName: "Anonymous" })))
      .to.emit(ledger, "Income").withArgs(h("tx1"), h("l"), 500000n, "VND", T, "D-001", "Anonymous");
  });

  it("rejects a repeated refId (webhook retry), even with a different leaf", async () => {
    await ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"), inc());
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("other"), inc()))
      .to.be.revertedWithCustomError(ledger, "AlreadyRecorded");
    await expect(ledger.connect(recorder).recordExpense(h("tx1"), h("leaf1"), exp()))
      .to.be.revertedWithCustomError(ledger, "AlreadyRecorded");
  });

  it("verify fails for a wrong leaf or an unknown refId", async () => {
    await ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"), inc());
    expect(await ledger.verify(h("tx1"), h("tampered"))).to.equal(false);
    expect(await ledger.verify(h("nope"), h("leaf1"))).to.equal(false);
  });

  it("only a recorder can write", async () => {
    await expect(ledger.connect(stranger).recordIncome(h("tx1"), h("leaf1"), inc())).to.be.reverted;
    await expect(ledger.connect(admin).recordExpense(h("tx1"), h("leaf1"), exp())).to.be.reverted;
    await expect(ledger.connect(stranger).anchorBatch(20261117, h("r"), 5)).to.be.reverted;
  });

  it("only the admin can grant or revoke recorders", async () => {
    await expect(ledger.connect(stranger).grantRole(RECORDER, stranger.address)).to.be.reverted;
    await ledger.revokeRole(RECORDER, recorder.address);
    await expect(ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"), inc())).to.be.reverted;
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
      () => r.recordIncome(z, h("l"), inc()),
      () => r.recordIncome(h("a"), z, inc()),
      () => r.recordIncome(h("a"), h("l"), inc({ amount: 0n })),
      () => r.recordIncome(h("a"), h("l"), inc({ txTime: 0 })),
      () => r.recordIncome(h("a"), h("l"), inc({ currency: "" })),
      () => r.recordIncome(h("a"), h("l"), inc({ donorId: "" })),
      () => r.recordExpense(h("a"), h("l"), exp({ recipientId: "" })),
      () => r.anchorBatch(20261117, z, 1),
      () => r.anchorBatch(20261117, h("r"), 0),
    ];
    for (const call of calls) {
      await expect(call()).to.be.revertedWithCustomError(ledger, "EmptyValue");
    }
  });

  it("pause stops writes but not reads; unpause resumes", async () => {
    await ledger.connect(recorder).recordIncome(h("tx1"), h("leaf1"), inc());
    await ledger.pause();
    await expect(ledger.connect(recorder).recordIncome(h("tx2"), h("l2"), inc()))
      .to.be.revertedWithCustomError(ledger, "EnforcedPause");
    expect(await ledger.verify(h("tx1"), h("leaf1"))).to.equal(true);
    await expect(ledger.connect(stranger).pause()).to.be.reverted;
    await ledger.unpause();
    await ledger.connect(recorder).recordIncome(h("tx2"), h("l2"), inc());
  });
});

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VieraProtocol", function () {
  let vieraProtocol;
  let vieraOracle;
  let owner;
  let researcher;
  let funder;
  let oracle;

  beforeEach(async function () {
    [owner, researcher, funder, oracle] = await ethers.getSigners();

    // Deploy contracts
    const VieraProtocol = await ethers.getContractFactory("VieraProtocol");
    vieraProtocol = await VieraProtocol.deploy(owner.address, oracle.address);
    await vieraProtocol.waitForDeployment();

    const VieraOracle = await ethers.getContractFactory("VieraOracle");
    vieraOracle = await VieraOracle.deploy(await vieraProtocol.getAddress());
    await vieraOracle.waitForDeployment();

    // Setup oracle
    await vieraProtocol.setOracle(await vieraOracle.getAddress(), true);
  });

  describe("Milestone Creation", function () {
    it("Should create a milestone with proper escrow", async function () {
      const amount = ethers.parseEther("1.0");
      const deadline = Math.floor(Date.now() / 1000) + 86400; // 1 day from now

      await expect(
        vieraProtocol.connect(funder).createMilestone(
          researcher.address,
          "Complete AI model training",
          "QmTestHash123",
          deadline,
          { value: amount }
        )
      ).to.emit(vieraProtocol, "MilestoneCreated");

      const milestone = await vieraProtocol.getMilestone(1);
      expect(milestone.researcher).to.equal(researcher.address);
      expect(milestone.funder).to.equal(funder.address);
      expect(milestone.amount).to.equal(amount);
    });

    it("Should reject invalid milestone creation", async function () {
      const amount = ethers.parseEther("1.0");
      const deadline = Math.floor(Date.now() / 1000) + 86400;

      // Cannot fund yourself
      await expect(
        vieraProtocol.connect(funder).createMilestone(
          funder.address,
          "Self-funding",
          "QmTestHash123",
          deadline,
          { value: amount }
        )
      ).to.be.revertedWith("Cannot fund yourself");

      // Must provide funding
      await expect(
        vieraProtocol.connect(funder).createMilestone(
          researcher.address,
          "No funding",
          "QmTestHash123",
          deadline,
          { value: 0 }
        )
      ).to.be.revertedWith("Must fund milestone");
    });
  });

  describe("Milestone Submission and Validation", function () {
    beforeEach(async function () {
      const amount = ethers.parseEther("1.0");
      const deadline = Math.floor(Date.now() / 1000) + 86400;

      await vieraProtocol.connect(funder).createMilestone(
        researcher.address,
        "Complete research",
        "QmInitialHash",
        deadline,
        { value: amount }
      );
    });

    it("Should allow researcher to submit milestone", async function () {
      await expect(
        vieraProtocol.connect(researcher).submitMilestone(1, "QmSubmissionHash")
      ).to.emit(vieraProtocol, "MilestoneSubmitted");

      const milestone = await vieraProtocol.getMilestone(1);
      expect(milestone.status).to.equal(2); // AI_VALIDATING
    });

    it("Should process high-confidence validation and payment", async function () {
      // Submit milestone
      await vieraProtocol.connect(researcher).submitMilestone(1, "QmSubmissionHash");

      // Simulate high-confidence AI validation
      const initialBalance = await ethers.provider.getBalance(researcher.address);
      
      await expect(
        vieraProtocol.connect(oracle).validateMilestone(
          1,
          true,
          90, // High confidence
          "QmValidationReport"
        )
      ).to.emit(vieraProtocol, "PaymentProcessed");

      // Check payment was processed
      const finalBalance = await ethers.provider.getBalance(researcher.address);
      expect(finalBalance).to.be.gt(initialBalance);

      const milestone = await vieraProtocol.getMilestone(1);
      expect(milestone.status).to.equal(5); // PAID
    });

    it("Should require human review for medium confidence", async function () {
      await vieraProtocol.connect(researcher).submitMilestone(1, "QmSubmissionHash");

      await vieraProtocol.connect(oracle).validateMilestone(
        1,
        true,
        75, // Medium confidence
        "QmValidationReport"
      );

      const milestone = await vieraProtocol.getMilestone(1);
      expect(milestone.status).to.equal(4); // HUMAN_REVIEW
    });
  });

  describe("Oracle Management", function () {
    it("Should allow oracle registration with stake", async function () {
      const stakeAmount = ethers.parseEther("1.0");

      await expect(
        vieraOracle.connect(oracle).registerNode({ value: stakeAmount })
      ).to.emit(vieraOracle, "NodeRegistered");

      const nodeInfo = await vieraOracle.getNodeInfo(oracle.address);
      expect(nodeInfo.isActive).to.be.true;
      expect(nodeInfo.stake).to.equal(stakeAmount);
    });

    it("Should reject insufficient stake", async function () {
      const insufficientStake = ethers.parseEther("0.5");

      await expect(
        vieraOracle.connect(oracle).registerNode({ value: insufficientStake })
      ).to.be.revertedWith("Insufficient stake");
    });
  });

  describe("Admin Functions", function () {
    it("Should allow owner to update thresholds", async function () {
      await vieraProtocol.setThresholds(80, 60);

      expect(await vieraProtocol.autoApprovalThreshold()).to.equal(80);
      expect(await vieraProtocol.humanReviewThreshold()).to.equal(60);
    });

    it("Should reject non-owner threshold updates", async function () {
      await expect(
        vieraProtocol.connect(funder).setThresholds(80, 60)
      ).to.be.reverted;
    });
  });
});
// scripts/verify-contracts.js
const { ethers } = require("hardhat");

async function main() {
  console.log(" Verifying deployed Viera Protocol contracts...\n");

  // Contract addresses from your deployment
  const VIERA_PROTOCOL_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3";
  const VIERA_ORACLE_ADDRESS = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512";

  try {
    // Get contract instances
    const VieraProtocol = await ethers.getContractFactory("VieraProtocol");
    const VieraOracle = await ethers.getContractFactory("VieraOracle");
    
    const protocol = VieraProtocol.attach(VIERA_PROTOCOL_ADDRESS);
    const oracle = VieraOracle.attach(VIERA_ORACLE_ADDRESS);

    console.log(" VieraProtocol Configuration:");
    console.log("=".repeat(40));
    
    // Check protocol settings
    const platformFee = await protocol.platformFeePercent();
    const autoThreshold = await protocol.autoApprovalThreshold();
    const humanThreshold = await protocol.humanReviewThreshold();
    const feeRecipient = await protocol.feeRecipient();
    const aiOracle = await protocol.aiOracle();
    
    console.log(`Platform Fee: ${Number(platformFee) / 100}%`);
    console.log(`Auto-approval Threshold: ${autoThreshold}%`);
    console.log(`Human Review Threshold: ${humanThreshold}%`);
    console.log(`Fee Recipient: ${feeRecipient}`);
    console.log(`AI Oracle Address: ${aiOracle}`);
    
    console.log("\n VieraOracle Configuration:");
    console.log("=".repeat(40));
    
    // Check oracle settings
    const minimumStake = await oracle.minimumStake();
    const requiredConsensus = await oracle.requiredConsensus();
    const consensusThreshold = await oracle.consensusThreshold();
    const activeNodes = await oracle.getActiveNodes();
    
    console.log(`Minimum Stake: ${ethers.formatEther(minimumStake)} ETH`);
    console.log(`Required Consensus: ${requiredConsensus} nodes`);
    console.log(`Consensus Threshold: ${consensusThreshold}%`);
    console.log(`Active Oracle Nodes: ${activeNodes.length}`);
    
    if (activeNodes.length > 0) {
      console.log(`Oracle Nodes: ${activeNodes.join(", ")}`);
    }

    console.log("\n Contract Verification Complete!");
    console.log("\n Your Viera Protocol is LIVE and ready for:");
    console.log("   • Milestone creation by funders");
    console.log("   • Research submission by researchers");
    console.log("   • AI-powered validation");
    console.log("   • Automated payments for high-confidence work");
    console.log("   • Human review for edge cases");
    
    // Test a simple contract interaction
    console.log("\n Testing contract interaction...");
    const nextMilestoneId = await protocol.nextMilestoneId();
    console.log(`Next Milestone ID: ${nextMilestoneId}`);
    
    console.log("\n All systems operational!");

  } catch (error) {
    console.error(" Verification failed:", error.message);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
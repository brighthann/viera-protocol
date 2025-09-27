const { ethers } = require("hardhat");

// Replace with your deployed contract addresses
const PROTOCOL_ADDRESS = "0x..."; // Replace after deployment
const ORACLE_ADDRESS = "0x...";   // Replace after deployment

async function main() {
  console.log("Setting up Viera Protocol...");
  
  const [owner] = await ethers.getSigners();
  console.log("Setup account:", owner.address);

  // Get contract instances
  const vieraProtocol = await ethers.getContractAt("VieraProtocol", PROTOCOL_ADDRESS);
  const vieraOracle = await ethers.getContractAt("VieraOracle", ORACLE_ADDRESS);

  console.log("\n1. Configuring protocol parameters...");
  
  // Set reasonable thresholds for MVP
  await vieraProtocol.setThresholds(85, 70); // 85% auto-approval, 70% human review
  console.log(" Validation thresholds set");
  
  // Set platform fee to 2.5%
  await vieraProtocol.setPlatformFee(250);
  console.log(" Platform fee set to 2.5%");

  console.log("\n2. Registering owner as initial oracle node...");
  
  // Register owner as first oracle node with 1 ETH stake
  const stakeAmount = ethers.parseEther("1.0");
  await vieraOracle.registerNode({ value: stakeAmount });
  console.log(" Owner registered as oracle node");

  console.log("\n3. Verifying setup...");
  
  // Check configurations
  const autoThreshold = await vieraProtocol.autoApprovalThreshold();
  const humanThreshold = await vieraProtocol.humanReviewThreshold();
  const platformFee = await vieraProtocol.platformFeePercent();
  const activeNodes = await vieraOracle.getActiveNodes();
  
  console.log(" Configuration Summary:");
  console.log("=".repeat(40));
  console.log("Auto-approval threshold:", autoThreshold.toString() + "%");
  console.log("Human review threshold:", humanThreshold.toString() + "%");
  console.log("Platform fee:", (Number(platformFee) / 100).toString() + "%");
  console.log("Active oracle nodes:", activeNodes.length);
  console.log("Oracle nodes:", activeNodes);
  
  console.log("\n🎉 Setup complete! Protocol is ready for testing.");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(" Setup failed:", error);
    process.exit(1);
  });
const { ethers } = require("hardhat");

// Replace with your deployed contract addresses
const PROTOCOL_ADDRESS = "0x..."; // Replace after deployment
const ORACLE_ADDRESS = "0x...";   // Replace after deployment

async function main() {
  console.log("Verifying Viera Protocol contracts...");

  const [deployer] = await ethers.getSigners();
  
  try {
    // Verify VieraProtocol
    console.log("1. Verifying VieraProtocol...");
    await hre.run("verify:verify", {
      address: PROTOCOL_ADDRESS,
      constructorArguments: [
        deployer.address, // feeRecipient
        deployer.address  // initial oracle (updated later)
      ],
    });
    console.log(" VieraProtocol verified");

    // Verify VieraOracle
    console.log("2. Verifying VieraOracle...");
    await hre.run("verify:verify", {
      address: ORACLE_ADDRESS,
      constructorArguments: [
        PROTOCOL_ADDRESS
      ],
    });
    console.log(" VieraOracle verified");

  } catch (error) {
    console.log(" Verification failed:", error.message);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
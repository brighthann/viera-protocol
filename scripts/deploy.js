const { ethers } = require("hardhat");

async function main() {
  console.log("Starting Viera Protocol deployment...");
  
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);
  console.log("Account balance:", ethers.formatEther(await deployer.provider.getBalance(deployer.address)));

  // Deploy VieraProtocol first
  console.log("\n1. Deploying VieraProtocol...");
  const VieraProtocol = await ethers.getContractFactory("VieraProtocol");
  
  // Set fee recipient to deployer for now (can be changed later)
  const feeRecipient = deployer.address;
  // AI Oracle will be set after oracle contract deployment
  const tempOracle = deployer.address;
  
  const vieraProtocol = await VieraProtocol.deploy(feeRecipient, tempOracle);
  await vieraProtocol.waitForDeployment();
  
  const protocolAddress = await vieraProtocol.getAddress();
  console.log(" VieraProtocol deployed to:", protocolAddress);

  // Deploy VieraOracle
  console.log("\n2. Deploying VieraOracle...");
  const VieraOracle = await ethers.getContractFactory("VieraOracle");
  const vieraOracle = await VieraOracle.deploy(protocolAddress);
  await vieraOracle.waitForDeployment();
  
  const oracleAddress = await vieraOracle.getAddress();
  console.log(" VieraOracle deployed to:", oracleAddress);

  // Update VieraProtocol with correct oracle address
  console.log("\n3. Setting up oracle connection...");
  await vieraProtocol.setOracle(oracleAddress, true);
  console.log(" Oracle connection established");

  // Verify deployment
  console.log("\n Deployment Summary:");
  console.log("=".repeat(50));
  console.log("VieraProtocol:", protocolAddress);
  console.log("VieraOracle:", oracleAddress);
  console.log("Fee Recipient:", feeRecipient);
  console.log("Deployer:", deployer.address);
  console.log("Network:", (await ethers.provider.getNetwork()).name);
  
  // Save deployment addresses for later use
  const deploymentInfo = {
    network: (await ethers.provider.getNetwork()).name,
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    deployer: deployer.address,
    contracts: {
      VieraProtocol: protocolAddress,
      VieraOracle: oracleAddress
    },
    deployedAt: new Date().toISOString()
  };
  
  console.log("\n Save this deployment info:");
  console.log(JSON.stringify(deploymentInfo, null, 2));
  
  return deploymentInfo;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(" Deployment failed:", error);
    process.exit(1);
  });
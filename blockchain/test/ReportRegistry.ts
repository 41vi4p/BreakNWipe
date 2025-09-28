import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.connect();

describe("ReportRegistryWithJson", function () {
  it("Should store and retrieve a report", async function () {
    const ReportRegistry = await ethers.getContractFactory("ReportRegistryWithJson");
    const reportRegistry = await ReportRegistry.deploy();
    await reportRegistry.waitForDeployment();

    const reportJSON = JSON.stringify({
      id: "123",
      name: "Chris Report",
      status: "verified",
    });

    const tx = await reportRegistry.storeReportJSON(reportJSON);
    await tx.wait();

    const hash = ethers.keccak256(ethers.toUtf8Bytes(reportJSON));
    const report = await reportRegistry.verifyReport(hash);

    expect(report.exists).to.equal(true);
  });
});

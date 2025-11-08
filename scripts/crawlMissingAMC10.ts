import aopsScraper from '../src/services/aopsScraper';
import fs from 'fs';
import path from 'path';

/**
 * Crawl Missing AMC 10 Tests
 * Downloads 2010, 2011, and 2021 Fall tests
 */
class MissingAMC10Crawler {
  private outputDir = 'crawled_data';

  // Define missing tests to crawl
  private testsToCrawl: Array<{year: number, variant: 'A' | 'B', season?: 'Fall' | 'Spring'}> = [
    // 2010
    { year: 2010, variant: 'A' as 'A' },
    { year: 2010, variant: 'B' as 'B' },
    // 2011
    { year: 2011, variant: 'A' as 'A' },
    { year: 2011, variant: 'B' as 'B' },
    // 2021 Fall (2021 Spring already exists)
    { year: 2021, variant: 'A' as 'A', season: 'Fall' as 'Fall' },
    { year: 2021, variant: 'B' as 'B', season: 'Fall' as 'Fall' },
  ];

  async crawl(): Promise<void> {
    console.log('🔍 Starting crawl of missing AMC 10 Tests');
    console.log('='.repeat(70));
    console.log(`Tests to crawl: ${this.testsToCrawl.length}`);
    console.log('='.repeat(70));

    try {
      // Ensure output directory exists
      this.ensureOutputDirectory();

      const allResults: any[] = [];

      for (const test of this.testsToCrawl) {
        await this.crawlSingleTest(test.year, test.variant, test.season, allResults);

        // Delay between tests to be respectful to the server
        await this.sleep(2000);
      }

      // Display final summary
      this.displayFinalSummary(allResults);

    } catch (error) {
      console.error('❌ Crawl failed:', error);
      throw error;
    }
  }

  private async crawlSingleTest(year: number, variant: 'A' | 'B', season: 'Fall' | 'Spring' | undefined, allResults: any[]): Promise<void> {
    const seasonStr = season ? ` ${season}` : '';
    const testName = `${year}${seasonStr} AMC 10${variant}`;

    console.log(`\n${'='.repeat(70)}`);
    console.log(`📚 Crawling ${testName}...`);
    console.log(`${'='.repeat(70)}`);

    try {
      const problems = await aopsScraper.scrapeSpecificTest(year, variant, 25, season);

      console.log(`✅ Successfully crawled ${problems.length} problems from ${testName}`);

      // Determine output filename
      let filename: string;
      if (season === 'Fall') {
        filename = `amc_${year}_fall_10${variant.toLowerCase()}_problems.json`;
      } else {
        filename = `amc_${year}_10${variant.toLowerCase()}_problems.json`;
      }

      // Save individual test file
      const outputPath = path.join(this.outputDir, filename);
      this.saveToFile(problems, outputPath, year, testName, season);

      // Add to combined results
      allResults.push({
        year,
        variant,
        season,
        test: testName,
        problemCount: problems.length,
        filePath: outputPath,
        metadata: {
          crawledAt: new Date().toISOString(),
          source: this.getSourceUrl(year, variant, season),
        }
      });

    } catch (error) {
      console.error(`❌ Error crawling ${testName}:`, error);
      allResults.push({
        year,
        variant,
        season,
        test: testName,
        error: error instanceof Error ? error.message : 'Unknown error',
        problemCount: 0
      });
    }
  }

  private getSourceUrl(year: number, variant: 'A' | 'B', season?: 'Fall' | 'Spring'): string {
    if (season === 'Fall') {
      return `https://artofproblemsolving.com/wiki/index.php/${year}_Fall_AMC_10${variant}_Problems`;
    }
    return `https://artofproblemsolving.com/wiki/index.php/${year}_AMC_10${variant}_Problems`;
  }

  private ensureOutputDirectory(): void {
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
      console.log(`✓ Created output directory: ${this.outputDir}`);
    }
  }

  private saveToFile(problems: any[], filePath: string, year: number, test: string, season?: 'Fall' | 'Spring'): void {
    const data = {
      metadata: {
        crawledAt: new Date().toISOString(),
        source: this.getSourceUrl(year, test.includes('10A') ? 'A' : 'B', season),
        year: year,
        test: test,
        season: season || 'Spring',
        totalProblems: problems.length
      },
      problems: problems
    };

    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    console.log(`💾 Saved to: ${filePath}`);
  }

  private displayFinalSummary(allResults: any[]): void {
    console.log('\n' + '='.repeat(70));
    console.log('📊 FINAL CRAWL SUMMARY');
    console.log('='.repeat(70));

    const successful = allResults.filter(r => r.problemCount > 0);
    const failed = allResults.filter(r => r.error);

    console.log(`\nTotal Tests Attempted: ${allResults.length}`);
    console.log(`✅ Successful: ${successful.length}`);
    console.log(`❌ Failed: ${failed.length}`);

    const totalProblems = successful.reduce((sum, r) => sum + r.problemCount, 0);
    console.log(`\nTotal Problems Crawled: ${totalProblems}`);

    if (successful.length > 0) {
      console.log(`\n✅ Successfully Crawled Tests:`);
      successful.forEach(r => {
        console.log(`   - ${r.test}: ${r.problemCount} problems`);
      });
    }

    if (failed.length > 0) {
      console.log(`\n❌ Failed Tests:`);
      failed.forEach(r => {
        console.log(`   - ${r.test}: ${r.error}`);
      });
    }

    console.log('\n' + '='.repeat(70));
    console.log('✨ Crawl process completed!');
    console.log('='.repeat(70));
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// CLI execution
const main = async () => {
  const crawler = new MissingAMC10Crawler();
  await crawler.crawl();
};

if (require.main === module) {
  main()
    .then(() => {
      console.log('\n✅ All crawl operations completed successfully');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Crawl script failed:', error);
      process.exit(1);
    });
}

export default MissingAMC10Crawler;
